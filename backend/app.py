import asyncio
import contextlib
import json
import logging
import os
import subprocess
import tempfile
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from iibin import Schema
from . import audio, inference, training
from .speech import SpeechSession
from .store import ROOT, VAR, db, init, new_thread, delete_thread, add_message

log=logging.getLogger('shopfloor')
SCHEMA=Schema(json.loads((ROOT/'shared/frame.json').read_text()))
OPERATIONS={'bootstrap','threads.list','threads.create','threads.delete','messages.list','message.send','voice.transcribe','audio.get','audio.played','faq.list','voices.list','voices.create','voices.activate','voice.preview','training.start','recordings.list','jobs.list','protocols.list','protocols.save','cache.list'}


def values(**kw):
    out=[]
    for key,v in kw.items():
        if v is None:continue
        out.append({'key':key,'flag' if isinstance(v,bool) else 'number' if isinstance(v,(int,float)) else 'text':v})
    return out


def row(kind,r,title='',text='',state='',extra=None):
    return {'id':str(r['id']),'kind':kind,'title':str(title),'text':str(text),'state':str(state),'created':str(r.get('created','')),'values':extra or []}


def list_threads():
    with db() as c:return [row('thread',dict(r),r['title']) for r in c.execute('SELECT * FROM thread ORDER BY created DESC,rowid DESC')]


def list_messages(tid):
    with db() as c:return [row(r['role'],dict(r),text=r['text'],extra=values(audio_id=r['audio_id'] or '',category=r['category'] or '')) for r in c.execute('SELECT * FROM message WHERE thread_id=? ORDER BY created,rowid',(tid,))]


def ensure_thread(tid):
    with db() as c:
        if not c.execute('SELECT 1 FROM thread WHERE id=?',(tid,)).fetchone():raise ValueError('Dieses Gespräch existiert nicht mehr.')


def lists(op,tid):
    with db() as c:
        if op=='faq.list':return [row('faq',dict(r),r['question'],r['answer']) for r in c.execute('SELECT * FROM faq ORDER BY rowid')]
        if op=='voices.list':return [row('voice',dict(r),r['name'],state=r['state'],extra=values(recordings=c.execute('SELECT COUNT(*) FROM recording WHERE voice_id=?',(r['id'],)).fetchone()[0],active=r['id']==audio.active_voice())) for r in c.execute('SELECT * FROM voice')]
        if op=='recordings.list':return [row('recording',dict(r),r['text'],extra=values(duration=r['duration'])) for r in c.execute('SELECT * FROM recording WHERE voice_id=? ORDER BY rowid',(tid,))]
        if op=='jobs.list':return [row('job',dict(r),r['kind']+' / '+r['category'],r['detail'],r['state']) for r in c.execute('SELECT * FROM job ORDER BY created DESC,rowid DESC LIMIT 60')]
        if op=='cache.list':return [row('variant',dict(r),r['category'],r['text'],r['voice_id']) for r in c.execute('SELECT * FROM answer_variant ORDER BY created DESC,rowid DESC LIMIT 100')]
        if op=='protocols.list':return [row('protocol',dict(r),r['id'][:8].upper(),state='passed' if r['passed'] else 'failed',extra=values(pressure=r['pressure'],drop=r['drop_value'],duration=r['duration'])) for r in c.execute('SELECT * FROM protocol ORDER BY created DESC,rowid DESC LIMIT 200')]
    return []


@asynccontextmanager
async def lifespan(app):
    init();inference.initialize()
    tasks=[asyncio.create_task(audio.worker()),asyncio.create_task(audio.seed_cache()),asyncio.create_task(training.worker())]
    yield
    for task in tasks:task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):await task

app=FastAPI(lifespan=lifespan)

@app.get('/health')
def health():return {'status':'ok','transport':'iibin-binary-websocket','models':inference.status,'mode':'local-demo'}

@app.post('/api/uploads/recording')
async def upload_recording(file:UploadFile=File(...),voice_id:str=Form(...),text:str=Form(...)):
    if not text.strip() or len(text)>1000:raise HTTPException(400,'Ein gültiger Aufnahmetext fehlt.')
    with db() as c:
        if not c.execute("SELECT 1 FROM voice WHERE id=? AND id!='thorsten'",(voice_id,)).fetchone():raise HTTPException(404,'Stimme nicht gefunden.')
    data=await file.read(20*1024*1024+1)
    if len(data)>20*1024*1024:raise HTTPException(413,'Aufnahme zu groß.')
    rid=str(uuid4());target=VAR/'recordings'/f'{rid}.wav'
    try:
        with tempfile.NamedTemporaryFile(suffix='.audio') as source:
            source.write(data);source.flush()
            await asyncio.to_thread(subprocess.run,['ffmpeg','-v','error','-y','-i',source.name,'-ac','1','-ar','22050','-t','30',str(target)],check=True,capture_output=True,timeout=20)
        with wave.open(str(target)) as w:duration=w.getnframes()/w.getframerate()
        if duration<1:raise ValueError('Aufnahme ist zu kurz.')
        with db() as c:c.execute('INSERT INTO recording VALUES(?,?,?,?,?)',(rid,voice_id,text.strip(),str(target),duration))
    except Exception as e:
        target.unlink(missing_ok=True)
        raise HTTPException(400,'Die Aufnahme konnte nicht verarbeitet werden.') from e
    # Uploads are the only non-WebSocket data path; response is also binary IIBIN.
    from fastapi.responses import Response
    return Response(SCHEMA.encode({'op':'recording.saved','rows':[{'id':rid,'text':text,'values':values(duration=duration)}]}),media_type='application/octet-stream')


async def handle(packet,send):
    op=packet.get('op');tid=packet.get('tid','');text=packet.get('text','')
    if op not in OPERATIONS:raise ValueError('Unbekannte Operation')
    if len(text)>3000:raise ValueError('Die Eingabe ist zu lang.')
    if op=='bootstrap':return {'rows':[{'id':k,'kind':'model','title':k,'state':v} for k,v in inference.status.items()],'voice':audio.active_voice(),'text':'Lokale Demo · Administrator','actions':list(OPERATIONS)}
    if op=='threads.list':return {'rows':list_threads()}
    if op=='threads.create':return {'tid':new_thread(),'rows':list_threads()}
    if op=='threads.delete':delete_thread(tid);return {'rows':list_threads()}
    if op=='messages.list':ensure_thread(tid);return {'rows':list_messages(tid)}
    if op in {'faq.list','voices.list','recordings.list','jobs.list','cache.list','protocols.list'}:return {'rows':lists(op,tid)}
    if op=='voices.create':
        vid=str(uuid4())
        with db() as c:c.execute("INSERT INTO voice(id,name,state) VALUES(?,?,'recording')",(vid,text.strip()[:60] or 'Meine Stimme'))
        return {'voice':vid,'rows':lists('voices.list','')}
    if op=='voices.activate':
        with db() as c:
            if not c.execute("SELECT 1 FROM voice WHERE id=? AND state='ready'",(packet.get('voice'),)).fetchone():raise ValueError('Diese Stimme ist noch nicht einsatzbereit.')
            c.execute("UPDATE setting SET value=? WHERE key='active_voice'",(packet['voice'],))
        return {'voice':packet['voice'],'rows':lists('voices.list','')}
    if op=='voice.preview':
        vid=packet.get('voice') or audio.active_voice();target=VAR/'audio'/f'preview-{vid}.wav'
        await asyncio.to_thread(inference.synthesize,'Hallo! Ich unterstütze dich bei der Ventilprüfung.',vid,target)
        return {'audio':target.read_bytes(),'voice':vid}
    if op=='training.start':return {'text':'Training wurde eingeplant. Den Fortschritt findest du unter Hintergrundaufträge.','state':'queued','rows':[{'id':training.prepare_training(packet.get('voice',''))}]}
    if op=='audio.get':
        with db() as c:r=c.execute('SELECT path FROM answer_variant WHERE id=?',(text,)).fetchone()
        if not r:raise ValueError('Audio nicht gefunden.')
        return {'audio':Path(r['path']).read_bytes()}
    if op=='audio.played':ensure_thread(tid);audio.acknowledge(tid,text);return {'state':'queued'}
    if op=='protocols.save':
        vals={v['key']:v.get('number',v.get('flag',v.get('text'))) for v in (packet.get('rows') or [{}])[0].get('values',[])}
        pressure=float(vals.get('pressure',0));drop=float(vals.get('drop',0));duration=float(vals.get('duration',10))
        if not 0<=pressure<=7 or not 0<=drop<=7 or not 0<=duration<=60:raise ValueError('Ungültige Messwerte')
        pid=str(uuid4())
        with db() as c:c.execute('INSERT INTO protocol(id,pressure,drop_value,passed,duration) VALUES(?,?,?,?,?)',(pid,pressure,drop,drop<=.1,duration))
        return {'rows':lists('protocols.list','')}
    if op=='voice.transcribe':
        data=packet.get('audio',b'')
        if not data or len(data)>8*1024*1024:raise ValueError('Ungültige Sprachaufnahme')
        return {'text':await asyncio.to_thread(inference.transcribe,data)}
    if op=='message.send':
        ensure_thread(tid)
        if len(text)>1000:raise ValueError('Eine Nachricht darf maximal 1.000 Zeichen enthalten.')
        if not text.strip():raise ValueError('Die Nachricht ist leer.')
        user_id=add_message(tid,'user',text)
        await send({'op':'message.accepted','tid':tid,'rows':[{'id':user_id,'kind':'user','text':text}]})
        started=time.perf_counter();category=await asyncio.to_thread(inference.decide,text)
        action_category=category
        dynamic_answer=None
        if category=='machine_pressure':
            context={v['key']:v.get('number') for r in packet.get('rows',[]) if r.get('id')=='machine' for v in r.get('values',[])}
            current=context.get('pressure')
            if isinstance(current,(int,float)) and 0<=current<=7:
                dynamic_answer='Der aktuelle Prüfdruck beträgt '+format(current,'.2f').replace('.',',')+' bar.'
                category='pressure:'+format(current,'.2f')
        voice=audio.active_voice();variant=audio.choose(tid,category,voice)
        answer=variant['text'] if variant else dynamic_answer or audio.canonical(category)
        mid=add_message(tid,'assistant',answer,category,variant['id'] if variant else '')
        actions=[action_category] if action_category.startswith(('nav_','machine_')) else []
        await send({'op':'message.reply','tid':tid,'text':answer,'actions':actions,'elapsed':(time.perf_counter()-started)*1000,'rows':[{'id':mid,'kind':'assistant','text':answer,'values':values(category=category,audio_id=variant['id'] if variant else '')}]})
        if not variant:
            # An unseen variation is created off the request path; never silently replay a used file.
            try:
                with db() as c:exists=c.execute('SELECT 1 FROM answer_variant WHERE category=? AND voice_id=?',(category,voice)).fetchone()
                variant=await asyncio.to_thread(audio.create_variant,category,voice,bool(exists),dynamic_answer)
                with db() as c:c.execute('UPDATE message SET audio_id=?,text=? WHERE id=?',(variant['id'],variant['text'],mid))
            except Exception:
                log.exception('Audio preparation failed')
                return {'state':'text_only'}
        # PCM blocks play as they arrive and can be cancelled between any two blocks.
        with wave.open(variant['path'], 'rb') as wav:
            if wav.getsampwidth()!=2 or wav.getnchannels()!=1:raise ValueError('PCM16-Mono-Audio erforderlich.')
            await send({'op':'audio.start','stream':mid,'tid':tid,'rate':wav.getframerate(),'text':variant['text'],'rows':[{'id':mid,'kind':'assistant','text':variant['text'],'values':values(audio_id=variant['id'])}]})
            while chunk:=wav.readframes(2048):
                await send({'op':'audio.chunk','stream':mid,'tid':tid,'audio':chunk})
                await asyncio.sleep(2048/wav.getframerate())
        await send({'op':'audio.end','stream':mid,'tid':tid})
        return {'state':'done'}
    raise ValueError('Operation nicht implementiert')


@app.websocket('/')
@app.websocket('/ws')
async def websocket(ws:WebSocket):
    origin=ws.headers.get('origin','')
    if origin and origin.split('://')[-1].split(':')[0] not in {'localhost','127.0.0.1'}:
        await ws.close(code=1008);return
    await ws.accept();lock=asyncio.Lock()
    async def raw_send(data):
        async with lock:await ws.send_bytes(SCHEMA.encode(data))
    tasks=set()
    session=SpeechSession(raw_send, handle)
    async def process(data):
        packet={}
        try:
            packet=SCHEMA.decode(data)
            async def send(payload):await raw_send({'id':packet.get('id',''),**payload})
            op=packet.get('op')
            if op=='voice.start':
                ensure_thread(packet.get('tid',''))
                if packet.get('rate')!=16000:raise ValueError('Der Audiostream muss 16 kHz verwenden.')
                session.interrupt(packet.get('turn',''))
                session.reset();session.stream=packet.get('stream','');session.tid=packet['tid']
                result={'state':'listening'}
            elif op=='voice.stop':
                session.stream='';session.reset();session.interrupt(packet.get('turn',''))
                result={'state':'stopped'}
            elif op=='response.interrupt':
                session.interrupt(packet.get('turn',''));session.reset()
                result={'state':'interrupted'}
            elif op=='message.send':result=await session.respond(packet)
            else:result=await handle(packet,send)
            await raw_send({'id':packet.get('id',''),'op':packet.get('op','')+'.result',**result})
        except (ValueError,RuntimeError) as e:
            with contextlib.suppress(Exception):await raw_send({'id':packet.get('id',''),'op':'error','error':str(e)})
        except Exception:
            log.exception('Operation failed')
            with contextlib.suppress(Exception):await raw_send({'id':packet.get('id',''),'op':'error','error':'Die Operation konnte nicht abgeschlossen werden. Details stehen im lokalen Serverprotokoll.'})
    try:
        while True:
            event=await ws.receive()
            if event['type']=='websocket.disconnect':break
            data=event.get('bytes')
            if data is None:await ws.close(code=1003);break
            # PCM input is processed in order, without an RPC/task per audio block.
            try:packet=SCHEMA.decode(data)
            except (ValueError,RuntimeError):
                await ws.close(code=1003);break
            if packet.get('op')=='voice.chunk':
                try:session.feed(packet)
                except ValueError as e:await raw_send({'op':'voice.status','state':'error','error':str(e)})
                continue
            if packet.get('op') in {'voice.start','voice.stop','response.interrupt'}:
                await process(data)
                continue
            if len(tasks)>=32:await ws.close(code=1013);break
            task=asyncio.create_task(process(data));tasks.add(task);task.add_done_callback(tasks.discard)
    except WebSocketDisconnect:pass
    finally:
        await session.close()
        # Accepted non-speech operations complete even if the browser disconnects.
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)

assets=ROOT/'frontend/dist/assets'
if assets.exists():app.mount('/assets',StaticFiles(directory=assets),name='assets')
@app.get('/{path:path}')
def surface(path:str):
    dist=(ROOT/'frontend/dist').resolve()
    public=(dist/path).resolve()
    if public.is_relative_to(dist) and public.is_file():return FileResponse(public)
    index=dist/'index.html'
    if not index.exists():raise HTTPException(503,'Frontend ist noch nicht gebaut.')
    return FileResponse(index)

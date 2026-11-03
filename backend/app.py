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
from . import audio, inference, training, lunar
from .speech import SpeechSession
from .responses import reply
from .store import ROOT, VAR, db, init, new_thread, delete_thread, add_message

log=logging.getLogger('shopfloor')
VOICE_ENABLED=os.getenv('ENABLE_VOICE','0')=='1'
SCHEMA=Schema(json.loads((ROOT/'shared/frame.json').read_text()))
OPERATIONS={'bootstrap','threads.list','threads.create','threads.delete','messages.list','message.send','voice.transcribe','audio.get','audio.played','faq.list','voices.list','voices.create','voices.activate','voice.preview','training.start','recordings.list','jobs.list','protocols.list','protocols.save','cache.list','lunar.runs.list','lunar.runs.get','lunar.runs.save','lunar.runs.delete'}


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
        if not c.execute('SELECT 1 FROM thread WHERE id=?',(tid,)).fetchone():raise ValueError('This conversation no longer exists.')


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
    init();lunar.init()
    tasks=[]
    if VOICE_ENABLED:
        inference.initialize()
        tasks=[asyncio.create_task(audio.worker()),asyncio.create_task(audio.seed_cache()),asyncio.create_task(training.worker())]
    else:
        inference.status.update({key:'disabled' for key in inference.status})
    yield
    for task in tasks:task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):await task

app=FastAPI(lifespan=lifespan)

@app.get('/health')
def health():
    if VOICE_ENABLED:inference.refresh_qwen_device()
    return {'status':'ok','transport':'iibin-binary-websocket','models':inference.status,'devices':inference.devices,'mode':'local-demo'}

@app.post('/api/uploads/recording')
async def upload_recording(file:UploadFile=File(...),voice_id:str=Form(...),text:str=Form(...)):
    if not text.strip() or len(text)>1000:raise HTTPException(400,'A valid recording transcript is required.')
    with db() as c:
        if not c.execute("SELECT 1 FROM voice WHERE id=? AND id!='lessac'",(voice_id,)).fetchone():raise HTTPException(404,'Voice not found.')
    data=await file.read(20*1024*1024+1)
    if len(data)>20*1024*1024:raise HTTPException(413,'Recording too large.')
    rid=str(uuid4());target=VAR/'recordings'/f'{rid}.wav'
    try:
        with tempfile.NamedTemporaryFile(suffix='.audio') as source:
            source.write(data);source.flush()
            await asyncio.to_thread(subprocess.run,['ffmpeg','-v','error','-y','-i',source.name,'-ac','1','-ar','22050','-t','30',str(target)],check=True,capture_output=True,timeout=20)
        with wave.open(str(target)) as w:duration=w.getnframes()/w.getframerate()
        if duration<1:raise ValueError('Recording is too short.')
        with db() as c:c.execute('INSERT INTO recording VALUES(?,?,?,?,?)',(rid,voice_id,text.strip(),str(target),duration))
    except Exception as e:
        target.unlink(missing_ok=True)
        raise HTTPException(400,'The recording could not be processed.') from e
    # Uploads are the only non-WebSocket data path; response is also binary IIBIN.
    from fastapi.responses import Response
    return Response(SCHEMA.encode({'op':'recording.saved','rows':[{'id':rid,'text':text,'values':values(duration=duration)}]}),media_type='application/octet-stream')


async def handle(packet,send):
    op=packet.get('op');tid=packet.get('tid','');text=packet.get('text','')
    if op not in OPERATIONS:raise ValueError('Unknown operation')
    if op.startswith('lunar.runs.'):
        return await asyncio.to_thread(lunar.handle,op,packet)
    if not VOICE_ENABLED and op in {'message.send','voice.transcribe','training.start','voice.preview'}:raise ValueError('Voice services are disabled. Start with VOICE=1.')
    if len(text)>3000:raise ValueError('Input is too long.')
    if op=='bootstrap':
        if VOICE_ENABLED:await asyncio.to_thread(inference.refresh_qwen_device)
        return {'rows':[{'id':k,'kind':'model','title':k,'state':v,'values':values(device=inference.devices[k])} for k,v in inference.status.items()],'voice':audio.active_voice(),'text':'Local demo · Administrator','actions':list(OPERATIONS)}
    if op=='threads.list':return {'rows':list_threads()}
    if op=='threads.create':return {'tid':new_thread(),'rows':list_threads()}
    if op=='threads.delete':delete_thread(tid);return {'rows':list_threads()}
    if op=='messages.list':ensure_thread(tid);return {'rows':list_messages(tid)}
    if op in {'faq.list','voices.list','recordings.list','jobs.list','cache.list','protocols.list'}:return {'rows':lists(op,tid)}
    if op=='voices.create':
        vid=str(uuid4())
        with db() as c:c.execute("INSERT INTO voice(id,name,state) VALUES(?,?,'recording')",(vid,text.strip()[:60] or 'My voice'))
        return {'voice':vid,'rows':lists('voices.list','')}
    if op=='voices.activate':
        with db() as c:
            if not c.execute("SELECT 1 FROM voice WHERE id=? AND state='ready'",(packet.get('voice'),)).fetchone():raise ValueError('This voice is not ready yet.')
            c.execute("UPDATE setting SET value=? WHERE key='active_voice'",(packet['voice'],))
        return {'voice':packet['voice'],'rows':lists('voices.list','')}
    if op=='voice.preview':
        vid=packet.get('voice') or audio.active_voice();target=VAR/'audio'/f'preview-{vid}.wav'
        await asyncio.to_thread(inference.synthesize,'Hello! I can help you with valve testing.',vid,target)
        return {'audio':target.read_bytes(),'voice':vid}
    if op=='training.start':return {'text':'Training has been queued. Progress is shown under background jobs.','state':'queued','rows':[{'id':training.prepare_training(packet.get('voice',''))}]}
    if op=='audio.get':
        with db() as c:r=c.execute('SELECT path FROM answer_variant WHERE id=?',(text,)).fetchone()
        if not r:raise ValueError('Audio not found.')
        return {'audio':Path(r['path']).read_bytes()}
    if op=='audio.played':ensure_thread(tid);audio.acknowledge(tid,text);return {'state':'queued'}
    if op=='protocols.save':
        vals={v['key']:v.get('number',v.get('flag',v.get('text'))) for v in (packet.get('rows') or [{}])[0].get('values',[])}
        pressure=float(vals.get('pressure',0));drop=float(vals.get('drop',0));duration=float(vals.get('duration',10))
        if not 0<=pressure<=7 or not 0<=drop<=7 or not 0<=duration<=60:raise ValueError('Invalid measurements')
        pid=str(uuid4())
        with db() as c:c.execute('INSERT INTO protocol(id,pressure,drop_value,passed,duration) VALUES(?,?,?,?,?)',(pid,pressure,drop,drop<=.1,duration))
        return {'rows':lists('protocols.list','')}
    if op=='voice.transcribe':
        data=packet.get('audio',b'')
        if not data or len(data)>8*1024*1024:raise ValueError('Invalid speech recording')
        return {'text':await asyncio.to_thread(inference.transcribe,data)}
    if op=='message.send':
        ensure_thread(tid)
        return await reply(packet,send)
    raise ValueError('Operation not implemented')


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
                if not VOICE_ENABLED:raise ValueError('Voice services are disabled. Start with VOICE=1.')
                ensure_thread(packet.get('tid',''))
                if packet.get('rate')!=16000:raise ValueError('The audio stream must use 16 kHz.')
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
            with contextlib.suppress(Exception):await raw_send({'id':packet.get('id',''),'op':'error','error':'The operation could not be completed. Details are in the local server log.'})
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
    if not index.exists():raise HTTPException(503,'The frontend has not been built.')
    return FileResponse(index)

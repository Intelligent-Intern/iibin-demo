"""Ordered speech output with three concurrent, bounded sentence synthesis jobs."""
import asyncio
import contextlib
import io
import json
import re
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from . import audio, inference
from .store import VAR, db, add_message

TTS = ThreadPoolExecutor(max_workers=3, thread_name_prefix='sentence-tts')


def machine_context(packet):
    return {v['key']:v.get('flag',v.get('number',v.get('text'))) for r in packet.get('rows',[]) if r.get('id')=='machine' for v in r.get('values',[])}


def protocols():
    with db() as c:
        counts=dict(c.execute('SELECT COUNT(*) AS total,COALESCE(SUM(passed),0) AS passed,MIN(created) AS first_created,MAX(created) AS last_created,AVG(pressure) AS average_pressure_bar,AVG(drop_value) AS average_drop_bar,AVG(duration) AS average_duration_seconds FROM protocol').fetchone())
        recent=[dict(row) for row in c.execute('SELECT id,pressure AS pressure_bar,drop_value AS drop_bar,passed,duration AS duration_seconds,created FROM protocol ORDER BY created DESC,rowid DESC LIMIT 20')]
    counts['failed']=counts['total']-counts['passed']
    return {'all_protocols':counts,'recent_protocols':recent,'scope':'Statistik über alle gespeicherten Prüfungen; Einzelwerte nur für die letzten 20 Prüfungen. Keine dokumentierten Fehlerursachen.'}


def interlock(category, state):
    running=state.get('stage') in {'filling','settling','measuring'}
    inserted=state.get('valveInserted',False);opened=state.get('guardOpen',True)
    action=category if category.startswith(('machine_','nav_')) else ''
    if category in {'machine_guard_open','machine_guard_close','machine_insert','machine_remove','machine_start','machine_close_start'}:
        if running:category='machine_blocked_running'
        elif category in {'machine_start','machine_close_start'} and not inserted:category='machine_blocked_valve'
        elif category=='machine_start' and opened:category='machine_blocked_start_guard'
        elif category in {'machine_insert','machine_remove'} and not opened and inserted!=(category=='machine_insert'):category='machine_blocked_guard'
        if category.startswith('machine_blocked_'):action=''
    if category=='machine_abort' and not running:category='machine_not_running';action=''
    if category=='machine_status':action=''
    return category,action


def values(**fields):
    return [{'key':key,'text':value} for key,value in fields.items()]


class Output:
    def __init__(self, tid, voice, send):
        self.tid,self.voice,self.send=tid,voice,send
        self.mid='';self.text='';self.category='';self.rate=0;self.pcm=[];self.variant=None
    def row(self):
        return {'id':self.mid,'kind':'assistant','text':self.text,'values':values(category=self.category,audio_id=self.variant['id'] if self.variant else '')}
    async def update(self,text=None,action=''):
        if text is not None:self.text=text
        first=not self.mid
        if first:self.mid=add_message(self.tid,'assistant',self.text,self.category)
        else:
            with db() as c:c.execute('UPDATE message SET text=?,category=? WHERE id=?',(self.text,self.category,self.mid))
        await self.send({'op':'message.reply' if first else 'message.update','tid':self.tid,'text':self.text,'rows':[self.row()],'actions':[action] if action else [],'state':'streaming'})
    async def wav(self,content,keep=True):
        with wave.open(io.BytesIO(content),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2:raise ValueError('PCM16-Mono-Audio erforderlich.')
            rate=wav.getframerate();pcm=wav.readframes(wav.getnframes())
        if not self.rate:
            self.rate=rate
            await self.send({'op':'audio.start','stream':self.mid,'tid':self.tid,'rate':rate,'rows':[self.row()]})
        if rate!=self.rate:raise ValueError('Die Abtastrate der Satzblöcke muss gleich bleiben.')
        if keep:self.pcm.append(pcm)
        for offset in range(0,len(pcm),4096):
            chunk=pcm[offset:offset+4096]
            await self.send({'op':'audio.chunk','stream':self.mid,'tid':self.tid,'audio':chunk})
            await asyncio.sleep(len(chunk)/(2*rate))
    async def finish(self):
        if self.pcm and not self.variant:
            with db() as c:existing=c.execute('SELECT id,path FROM answer_variant WHERE category=? AND voice_id=? AND text=?',(self.category,self.voice,self.text)).fetchone()
            if existing:self.variant=dict(existing)
            else:
                vid=str(uuid4());path=VAR/'audio'/f'{vid}.wav'
                with wave.open(str(path),'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(self.rate);wav.writeframes(b''.join(self.pcm))
                try:
                    with db() as c:
                        c.execute('INSERT OR IGNORE INTO answer_variant(id,category,voice_id,text,path) VALUES(?,?,?,?,?)',(vid,self.category,self.voice,self.text,str(path)))
                        existing=c.execute('SELECT id,path FROM answer_variant WHERE category=? AND voice_id=? AND text=?',(self.category,self.voice,self.text)).fetchone()
                    self.variant=dict(existing)
                    if self.variant['id']!=vid:path.unlink(missing_ok=True)
                except BaseException:path.unlink(missing_ok=True);raise
        if self.variant:
            with db() as c:c.execute('UPDATE message SET audio_id=?,text=?,category=? WHERE id=?',(self.variant['id'],self.text,self.category,self.mid))
        await self.send({'op':'message.done','tid':self.tid,'rows':[self.row()],'state':'done'})
        if self.rate:await self.send({'op':'audio.end','stream':self.mid,'tid':self.tid,'rows':[self.row()]})


async def static_sentences(text):
    for sentence in re.split(r'(?<=[.!?])\s+',text.strip()):
        if sentence:yield sentence


async def model_sentences(model):
    iterator=model.sentences();sentinel=object()
    try:
        while True:
            sentence=await asyncio.to_thread(next,iterator,sentinel)
            if sentence is sentinel:return
            yield sentence
    finally:
        model.stopped.set()
        if model.response:
            # Release the reader and Ollama generation even when interrupted mid-sentence.
            asyncio.get_running_loop().run_in_executor(None,model.cancel)


async def sentence_audio(output, source):
    queue=asyncio.Queue(maxsize=3);slots=asyncio.Semaphore(3);jobs=set()
    async def produce():
        try:
            async for sentence in source:
                await slots.acquire()
                await output.update((output.text+' '+sentence).strip())
                future=asyncio.get_running_loop().run_in_executor(TTS,inference.synthesize_sentence,sentence,output.voice)
                jobs.add(future);future.add_done_callback(jobs.discard)
                await queue.put(future)
        except asyncio.CancelledError:raise
        except Exception as error:
            await queue.put(error)
        else:await queue.put(None)
    producer=asyncio.create_task(produce())
    try:
        while True:
            job=await queue.get()
            if job is None:break
            if isinstance(job,Exception):raise job
            slots.release()
            await output.wav(await job)
        await producer
    finally:
        producer.cancel()
        for job in jobs:job.cancel()
        with contextlib.suppress(asyncio.CancelledError):await producer
        with contextlib.suppress(Exception):await source.aclose()


async def reply(packet,send):
    tid,text=packet['tid'],packet.get('text','').strip()
    if not text or len(text)>1000:raise ValueError('Eine Nachricht muss zwischen 1 und 1.000 Zeichen enthalten.')
    with db() as c:history=[{'role':r['role'],'content':r['text'][:1000]} for r in reversed(c.execute('SELECT role,text FROM message WHERE thread_id=? ORDER BY rowid DESC LIMIT 2',(tid,)).fetchall())]
    uid=add_message(tid,'user',text)
    await send({'op':'message.accepted','tid':tid,'rows':[{'id':uid,'kind':'user','text':text}]})
    context=machine_context(packet);voice=audio.active_voice();output=Output(tid,voice,send)
    decision=asyncio.create_task(asyncio.to_thread(inference.decide,text,context,history))
    try:
        category,action=interlock(await decision,context);output.category=category
        dynamic=None
        if category=='machine_status':
            states={'ready':'bereit','filling':'im Druckaufbau','settling':'in der Stabilisierung','measuring':'in der Messphase','passed':'bestanden','failed':'fehlgeschlagen'}
            dynamic='Die Prüfung ist '+states.get(context.get('stage'),'noch nicht geöffnet')+'. Die Schutzhaube ist '+('geöffnet' if context.get('guardOpen',True) else 'geschlossen')+'. Das Ventil ist '+('eingelegt.' if context.get('valveInserted') else 'nicht eingelegt.')
        elif category=='machine_pressure' and isinstance(context.get('pressure'),(int,float)):
            dynamic='Der aktuelle Prüfdruck beträgt '+format(context['pressure'],'.2f').replace('.',',')+' bar.'
        if category in {'fallback','protocol_summary'} or category.startswith('faq_') and not audio.choose(tid,category,voice):
            if not output.mid:await output.update('')
            facts={'protocols':protocols()} if category=='protocol_summary' else {}
            if category.startswith('faq_'):
                with db() as c:faq=c.execute('SELECT question,answer FROM faq WHERE id=?',(category,)).fetchone()
                if faq:facts['faq']=dict(faq)
            output.category='generated:'+category if category!='fallback' else 'conversation'
            await sentence_audio(output,model_sentences(inference.AnswerStream(text,facts,history)))
        elif dynamic is not None:
            output.category='live:'+category
            await sentence_audio(output,static_sentences(dynamic))
        else:
            variant=audio.choose(tid,category,voice)
            answer=variant['text'] if variant else audio.canonical(category)
            await output.update(answer,action)
            if variant:
                output.variant=variant
                await output.wav(Path(variant['path']).read_bytes())
            else:await sentence_audio(output,static_sentences(answer))
        if not output.text:
            await sentence_audio(output,static_sentences('Was möchtest du wissen oder am Prüfstand tun?'))
        await output.finish()
        return {'state':'done'}
    except Exception:
        if output.rate:await send({'op':'audio.end','stream':output.mid,'tid':tid})
        raise
    finally:
        decision.cancel()

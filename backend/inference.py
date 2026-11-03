"""CPU speech workers and CPU/CUDA text generation outside the event loop."""
import io
import difflib
import json
import os
import re
import threading
import time
import urllib.request
import wave
from pathlib import Path
from .store import ROOT, VAR, db

_lock = threading.Lock()
_voice_lock = threading.Lock()
_stt_lock = threading.Lock()
agent = None
recognizer = None
voices = {}
devices = {'laya':'cpu','piper':'cpu','whisper':'cpu','qwen':'loading'}
status = {'laya':'loading', 'piper':'loading', 'whisper':'loading', 'qwen':'loading'}


def request_json(url, payload=None, timeout=120):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:return json.load(r)


def load_laya():
    global agent
    import torch
    from laya import load
    torch.set_num_threads(int(os.getenv('CPU_THREADS','4')))
    agent = load('convaiinnovations/laya', subfolder='multilingual', device='cpu')
    status['laya']='ready'


def load_piper():
    target = VAR/'voices/lessac.onnx'
    url='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx'
    for suffix in ['', '.json']:
        path=Path(str(target)+suffix)
        if not path.exists():
            temp=Path(str(path)+'.part')
            with urllib.request.urlopen(url+suffix,timeout=120) as source, temp.open('wb') as dest:
                while chunk:=source.read(1024*1024):dest.write(chunk)
            temp.replace(path)
    from piper import PiperVoice
    voices['lessac']=PiperVoice.load(str(target), use_cuda=False)
    with db() as c:c.execute("UPDATE voice SET model=?,config=?,state='ready' WHERE id='lessac'",(str(target),str(target)+'.json'))
    status['piper']='ready'


def load_whisper():
    global recognizer
    from faster_whisper import WhisperModel
    recognizer=WhisperModel('tiny',device='cpu',compute_type='int8',cpu_threads=int(os.getenv('CPU_THREADS','4')),download_root=str(VAR/'models'))
    status['whisper']='ready'


def refresh_qwen_device():
    try:
        running=request_json(os.getenv('OLLAMA_URL','http://127.0.0.1:11435')+'/api/ps',timeout=1)
        model=os.getenv('QWEN_MODEL','qwen3.5:2b')
        current=next((item for item in running.get('models',[]) if item.get('name')==model),None)
        if current is None:devices['qwen']='standby';return
        vram=current.get('size_vram',0)
        devices['qwen']='gpu' if vram and vram>=current.get('size',0) else 'hybrid' if vram else 'cpu'
    except Exception:pass


def load_qwen():
    base=os.getenv('OLLAMA_URL','http://127.0.0.1:11435')
    model=os.getenv('QWEN_MODEL','qwen3.5:2b')
    for _ in range(180):
        try:
            tags=request_json(base+'/api/tags',timeout=3)
            if any(m.get('name')==model for m in tags.get('models',[])):
                request_json(base+'/api/generate',{'model':model,'prompt':'','stream':False,'options':{'num_ctx':2048}},timeout=60)
                refresh_qwen_device()
                status['qwen']='ready'
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('The Qwen model is not ready. Check the Ollama download.')


def warm_model(name, fn):
    try:fn()
    except Exception as e:status[name]='error: '+str(e)[:240]


def initialize():
    for name,fn in [('laya',load_laya),('piper',load_piper),('whisper',load_whisper),('qwen',load_qwen)]:
        threading.Thread(target=warm_model,args=(name,fn),daemon=True,name='load-'+name).start()


ACTIONS = {'greeting': 'A greeting or farewell, such as hello, good morning or goodbye.', 'nav_machine': 'Open or show the valve test bench.', 'nav_dashboard': 'Return to the dashboard or overview.', 'nav_protocols': 'Open saved inspection reports or results.', 'nav_knowledge': 'Open FAQ or help.', 'nav_voice': 'Record a custom voice or open voice management.', 'machine_guard_open': 'Open the safety guard or report that it is open.', 'machine_close_start': 'Combined command: close the safety guard and then start the test.', 'machine_abort': 'Abort, stop or end the running or paused test. Not merely pause it.', 'machine_guard_close': 'Close the safety guard without starting a test, or report that it is closed.', 'machine_insert': 'Insert the valve or confirm that it has already been inserted. Not a request for instructions.', 'machine_remove': 'Remove the valve or report that it has been removed.', 'machine_start': 'Start the simulated pressure test now.', 'machine_pause': 'Pause or resume the running test.', 'machine_reset': 'Reset the simulated test.', 'protocol_summary': 'Ask about actual saved inspection reports, measurements, results or statistics: count, failure rate, latest result or comparison. Not general test procedure and not opening the report view.', 'machine_status': 'Ask about the current test bench state, guard or inserted valve.', 'machine_pressure': 'Ask about current test pressure.', 'fallback': 'No matching command or FAQ question; unclear or unrelated input.'}


def machine_command(text):
    english=text.casefold()
    report=bool(re.search(r'\b(reports?|results?|inspections?|tests?)\b',english))
    if report and re.search(r'\b(how many|count|total|failed|failure rate|statistics|latest|last result|summary)\b',english):return 'protocol_summary'
    question=bool(re.search(r'\b(how|why|when|what|explain)\b|\b(can|should|must) i\b',english))
    if question:return None
    guard=bool(re.search(r'\b(guard|cover|hood|shield|door)\b',english))
    test=bool(re.search(r'\b(test|inspection|cycle)\b',english))
    if (guard or test or 'valve' in english) and re.search(r"\b(do not|dont|never|not|without)\b|don.t",english):return 'fallback'
    start=test and bool(re.search(r'\b(start|begin|run)\b',english))
    close=guard and bool(re.search(r'\b(close|closed|shut|lower)\b',english))
    if (test and re.search(r'\b(abort|cancel|stop|end)\b',english)) or english.strip(' .!?') in {'abort','stop'}:return 'machine_abort'
    if close and start:return 'machine_close_start'
    if close:return 'machine_guard_close'
    if guard and re.search(r'\b(open|opened|raise|lift|unlock)\b',english):return 'machine_guard_open'
    if 'valve' in english:
        if re.search(r'\b(insert|inserted|place|placed|load|loaded)\b',english):return 'machine_insert'
        if re.search(r'\b(remove|removed|take out|unload)\b',english):return 'machine_remove'
    if test and re.search(r'\b(pause|resume|continue)\b',english):return 'machine_pause'
    if test and re.search(r'\b(reset|restart)\b',english):return 'machine_reset'
    if start:return 'machine_start'
    text=text.casefold().replace('ä','ae').replace('ö','oe').replace('ü','ue')
    vocabulary=['schutzhaube','schutzklappe','eingeliegt','eingelegt']
    def repair(match):
        token=match.group();near=difflib.get_close_matches(token,vocabulary,n=1,cutoff=.78)
        return near[0] if near else token
    text=re.sub(r'\b\w+\b',repair,text).replace('eingeliegt','eingelegt')
    if re.search(r'\b(wie ?viele|anzahl|bilanz|statistik|fehlerquote|ausschuss|fehlgeschlagen|durchgefallen)\b',text) and re.search(r'pruef|protokoll|ausschuss',text):return 'protocol_summary'
    if (re.search(r'pruefprotokoll|pruefergebnis|pruefung|messwert',text)
            and re.search(r'\b(unsere?\w*|meine?\w*|bisherig\w*|letzte\w*|heutige\w*|gestrige\w*)\b',text)
            and re.search(r'\?|\b(was|wie|welch\w*|warum|sag\w*|erzaehl\w*|bericht\w*|zusammen\w*|auswert\w*|analys\w*|ueberblick|vergleich\w*)\b',text)
            and not re.search(r'\b(oeffn\w*|anzeigen|ansicht|start\w*|abbrech\w*|pausier\w*|fortsetz\w*|zuruecksetz\w*)\b',text)):
        return 'protocol_summary'
    # Knowledge questions remain classifier input; requests such as "kannst du" are commands.
    if re.search(r'\b(wie|warum|wann|wieso|weshalb|erklaer\w*)\b|\b(kann|darf|soll|muss) ich\b',text):return None
    machine=bool(re.search(r'\b(ventil|pruefung|prueflauf|pruefzyklus|druckpruefung|test|schutzhaube|schutzklappe|haube|klappe|abdeckung|deckel|tuer)\b',text))
    if machine and re.search(r'\b(nicht|kein\w*|ohne)\b',text):return 'fallback'
    test=bool(re.search(r'\b(pruefung|prueflauf|pruefzyklus|druckpruefung|test)\b',text))
    if (test and re.search(r'\b(abbrech\w*|abbruch|stopp?\w*|beend\w*)\b',text)) or text.strip(' .!?') in {'stop','stopp','abbrechen'}:return 'machine_abort'
    start=test and bool(re.search(r'\b(start\w*|beginn\w*|los)\b',text))
    guard=bool(re.search(r'\b(schutzhaube|schutzklappe|haube|klappe|abdeckung|deckel|tuer)\b',text))
    close=guard and bool(re.search(r'\b(schliess\w*|geschlossen|zu|zumachen|runter\w*|herunter\w*|senk\w*)\b',text))
    if close and start:return 'machine_close_start'
    if close:return 'machine_guard_close'
    if guard and re.search(r'\b(oeffn\w*|auf|aufmachen|geoeffnet|hoch\w*|heb\w*|anheb\w*|entriegel\w*)\b',text):return 'machine_guard_open'
    if re.search(r'\bventil\b',text):
        if re.search(r'\b(eingelegt|einleg\w*|eingesetzt|einsetz\w*)\b',text):return 'machine_insert'
        if re.search(r'\b(entnehm\w*|entnommen|herausnehm\w*|herausgenommen|rausnehm\w*)\b',text):return 'machine_remove'
    if start:return 'machine_start'
    return None


def faq_terms(text):
    text=text.casefold().replace('ä','ae').replace('ö','oe').replace('ü','ue')
    stop={'wie','was','wann','warum','ist','sind','die','der','das','den','dem','ein','eine','einen','einem','ich','du','es','man','mir','bitte','kann','kannst','muss','soll','wird','werden','dieser','dieses','mein','meine','so','fuer','und','oder','mit','dann','in','von','zu','zum','auf','ab','am','im','hier'}
    stop|={'how','what','when','why','is','are','the','a','an','i','you','it','to','of','on','for','with','and','or','can','do','does','this','my','me','please'}
    aliases={'lange':'dauer','dauert':'dauer','dauern':'dauer','braucht':'dauer','zeit':'dauer','test':'pruefung','pruefzyklus':'pruefung','ablauf':'verfahren','funktioniert':'verfahren','methode':'verfahren','schutzhaube':'haube','schutzklappe':'haube','geschlossen':'schliessen','schliesse':'schliessen','pruefdruck':'druck','ergebnisse':'ergebnis','protokolle':'ergebnis','undicht':'leck','leckage':'leck','anhalten':'pause','pausieren':'pause','starte':'start','starten':'start'}
    aliases.update({'testing':'test','inspection':'test','leakage':'leak','leaky':'leak','leaks':'leak','procedure':'method','works':'method','work':'method','long':'duration','takes':'duration','time':'duration','results':'result','reports':'result','stop':'pause','start':'start','starting':'start','closed':'close','closing':'close'})
    return {aliases.get(word,word) for word in re.findall(r'\w+',text) if word not in stop}


def relevant_faq(text):
    query=faq_terms(text)
    with db() as c:catalog=[dict(row) for row in c.execute('SELECT id,question,answer FROM faq')]
    for row in catalog:
        terms=faq_terms(row['question'])
        overlap=query&terms
        row['match']=2*len(overlap)/max(1,len(query)+len(terms)) if overlap-{'pruefung','ventil','test','valve'} else 0
    return sorted(catalog,key=lambda row:row['match'],reverse=True)


def decide(text, context=None, history=None):
    command=machine_command(text)
    if command:return command
    if re.fullmatch(r'\s*(hello|hi|hey|good (morning|afternoon|evening)|goodbye|bye|hallo|guten (morgen|tag|abend)|moin|servus|tschuess)[!. ]*',text.casefold()):return 'greeting'
    matches=relevant_faq(text)
    if agent is None:
        return matches[0]['id'] if matches and matches[0]['match']>=.78 else 'fallback'
    knowledge=bool(re.search(r'\b(what|who|which|how|why|when|explain)\b|\b(can|should|must) i\b',text.casefold())) or bool(re.search(r'\b(was|wer|welche\w*|wie|warum|wann|wieso|weshalb)\b|\b(kann|darf|soll|muss) ich\b',text.casefold()))
    if agent is not None:
        criteria={k:v for k,v in ACTIONS.items() if k not in {'greeting','fallback'} and (not knowledge or k in {'protocol_summary','machine_status','machine_pressure'})}
        criteria['none']='No matching machine command, report query or live-state query; general conversation, unclear or unrelated input.'
        with _lock:
            prediction=agent.predict(text,{'action':{'type':'choice','instructions':'Recognize machine commands and queries about saved inspection reports or live machine state. Do not execute commands for instructions, negations or conversation. Select none without a matching branch.','criteria':criteria}},lang='en')
        result=prediction.get('answers',prediction)['action'];probabilities=result.get('probabilities',{})
        ranked=sorted(probabilities.values(),reverse=True)
        if result['choice']!='none' and probabilities.get(result['choice'],0)>=.72 and (len(ranked)<2 or ranked[0]-ranked[1]>=.18):return result['choice']
    if matches and matches[0]['match']>=.78:return matches[0]['id']
    with db() as c:faqs=c.execute('SELECT * FROM faq').fetchall()
    criteria={r['id']:r['question']+' '+r['answer'] for r in faqs}
    criteria['none']='None of these FAQs answers the question; general conversation, unclear input or another topic.'
    with _lock:
        result=agent.predict(text,{'faq':{'type':'choice','instructions':'Select an FAQ only if it answers the specific question. Do not invent a connection. Otherwise select none.','criteria':criteria}},lang='en')
    answer=result.get('answers',result)['faq'];choice=answer['choice']
    return choice if choice in criteria and choice!='none' and answer.get('probabilities',{}).get(choice,0)>=.65 else 'fallback'


_parallel_voice = threading.local()

def synthesize_sentence(text, voice_id):
    """A private one-thread ONNX session per TTS worker permits real parallel synthesis."""
    import onnxruntime as ort
    from piper import PiperVoice
    from piper.config import PiperConfig
    models=getattr(_parallel_voice,'models',None)
    if models is None:models=_parallel_voice.models={}
    if voice_id not in models:
        with db() as c:record=c.execute("SELECT model,config FROM voice WHERE id=? AND state='ready'",(voice_id,)).fetchone()
        if not record:raise RuntimeError('The response voice is not ready.')
        opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
        models[voice_id]=PiperVoice(session=ort.InferenceSession(record['model'],sess_options=opts,providers=['CPUExecutionProvider']),config=PiperConfig.from_dict(json.loads(Path(record['config']).read_text())))
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:models[voice_id].synthesize_wav(text,wav)
    return output.getvalue()


class AnswerStream:
    def __init__(self,text,context,history):
        self.stopped=threading.Event();self.response=None
        self.context_size=4096 if context.get('protocols') else 2048
        self.messages=[{'role':'system','content':'You are LCC, an English-speaking voice assistant in a valve leak-testing system. You can also answer general questions. Answer directly and factually in one to three short sentences without Markdown; ask a brief clarification when needed. For this machine, its functions and inspection reports, use only the supplied facts. Prior conversation is not evidence. Do not invent features, restrictions, measurements or actions performed. If system information is missing, say that you do not know more about the machine and can answer other general questions. Use only facts relevant to the current question, respect their stated scope, and do not infer undocumented causes of failed inspections. Always respond in English.'},*history,{'role':'user','content':json.dumps({'question':text,'facts':context},ensure_ascii=False)}]
    def cancel(self):
        self.stopped.set()
        if self.response:
            # Closing the HTTP stream also cancels Ollama's remaining generation.
            try:self.response.close()
            except Exception:pass
    def sentences(self):
        payload={'model':os.getenv('QWEN_MODEL','qwen3.5:2b'),'stream':True,'think':False,'messages':self.messages,'options':{'num_predict':260,'num_ctx':self.context_size,'temperature':.35,'presence_penalty':0,'repeat_penalty':1.05,'num_thread':int(os.getenv('CPU_THREADS','4'))}}
        request=urllib.request.Request(os.getenv('OLLAMA_URL','http://127.0.0.1:11435')+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        pending='';count=0
        with urllib.request.urlopen(request,timeout=45) as response:
            self.response=response
            for line in response:
                if self.stopped.is_set():return
                part=json.loads(line);pending+=part.get('message',{}).get('content','')
                while True:
                    match=re.search(r'(?<=[.!?])(?:\s+|$)',pending)
                    if not match:break
                    sentence=pending[:match.end()].strip();pending=pending[match.end():]
                    if sentence:
                        yield sentence;count+=1
                        if count>=6:return
                if len(pending)>260:
                    split=pending.rfind(' ',0,240)
                    if split>0:
                        yield pending[:split].strip();pending=pending[split:].lstrip();count+=1
                        if count>=6:return
                if part.get('done'):break
            if pending.strip():yield pending.strip()
        self.response=None


def synthesize(text, voice_id, output):
    with _voice_lock:
        if voice_id not in voices:
            with db() as c:voice=c.execute('SELECT * FROM voice WHERE id=? AND state=?',(voice_id,'ready')).fetchone()
            if not voice:raise RuntimeError('The selected voice is not ready.')
            from piper import PiperVoice
            voices[voice_id]=PiperVoice.load(voice['model'],use_cuda=False)
        with wave.open(str(output),'wb') as wav:voices[voice_id].synthesize_wav(text,wav)


def transcribe(audio):
    if recognizer is None:raise RuntimeError('Speech recognition is still being prepared.')
    import numpy as np
    import subprocess
    try:
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000:
                raise ValueError('PCM normalization required')
            pcm=wav.readframes(16000*30)
    except (wave.Error, EOFError, ValueError):
        pcm=subprocess.run(['ffmpeg','-v','error','-i','pipe:0','-f','s16le','-ac','1','-ar','16000','-t','30','pipe:1'],input=audio,capture_output=True,check=True,timeout=15).stdout
    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
    if not samples.size:return ''
    with _stt_lock:
        # Supplying samples bypasses the incompatible PyAV file decoder entirely.
        segments,info=recognizer.transcribe(samples,language='en',beam_size=3,vad_filter=True,condition_on_previous_text=False,initial_prompt='Valve test bench. Open safety guard. Close safety guard. Valve inserted. Start, pause or abort test. Inspection reports. Failed tests.')
        return ' '.join(s.text.strip() for s in segments).strip()


APPROVED_VARIANTS=json.loads((ROOT/'content/answer-variants.json').read_text())

class VariantsExhausted(Exception):
    pass

def approved_variants(category, base):
    if category.startswith('pressure:'):
        return [base, 'The measurement is '+base.removeprefix('The current test pressure is '), 'The current reading is '+base.removeprefix('The current test pressure is ')]
    return [base, *APPROVED_VARIANTS.get(category, [])]

def paraphrase(text, existing, category):
    # Model output is an index into reviewed phrases, never playable free text.
    options=[v for v in approved_variants(category,text) if v not in existing]
    if not options:raise VariantsExhausted('All approved phrasings are already cached.')
    return options[0]

"""CPU-only speech and typed decisions; model work stays outside the event loop."""
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
    target = VAR/'voices/thorsten.onnx'
    url='https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx'
    for suffix in ['', '.json']:
        path=Path(str(target)+suffix)
        if not path.exists():
            temp=Path(str(path)+'.part')
            with urllib.request.urlopen(url+suffix,timeout=120) as source, temp.open('wb') as dest:
                while chunk:=source.read(1024*1024):dest.write(chunk)
            temp.replace(path)
    from piper import PiperVoice
    voices['thorsten']=PiperVoice.load(str(target), use_cuda=False)
    with db() as c:c.execute("UPDATE voice SET model=?,config=?,state='ready' WHERE id='thorsten'",(str(target),str(target)+'.json'))
    status['piper']='ready'


def load_whisper():
    global recognizer
    from faster_whisper import WhisperModel
    recognizer=WhisperModel('tiny',device='cpu',compute_type='int8',cpu_threads=int(os.getenv('CPU_THREADS','4')),download_root=str(VAR/'models'))
    status['whisper']='ready'


def load_qwen():
    base=os.getenv('OLLAMA_URL','http://127.0.0.1:11435')
    model=os.getenv('QWEN_MODEL','qwen3.5:2b')
    for _ in range(180):
        try:
            tags=request_json(base+'/api/tags',timeout=3)
            if any(m.get('name')==model for m in tags.get('models',[])):
                request_json(base+'/api/generate',{'model':model,'prompt':'','stream':False,'options':{'num_gpu':0,'num_ctx':2048}},timeout=60)
                status['qwen']='ready'
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('Das Qwen-Modell ist noch nicht verfügbar. Prüfe den Ollama-Download.')


def warm_model(name, fn):
    try:fn()
    except Exception as e:status[name]='error: '+str(e)[:240]


def initialize():
    for name,fn in [('laya',load_laya),('piper',load_piper),('whisper',load_whisper),('qwen',load_qwen)]:
        threading.Thread(target=warm_model,args=(name,fn),daemon=True,name='load-'+name).start()


ACTIONS = {
    'greeting':'Eine reine Begrüßung oder Verabschiedung, z.B. Hallo, Guten Morgen, Tschüss.',
    'nav_machine':'Den Ventilprüfstand oder die Ventilprüfung öffnen/anzeigen.',
    'nav_dashboard':'Zur Übersicht oder zum Dashboard zurückgehen.',
    'nav_protocols':'Gespeicherte Prüfprotokolle oder Prüfergebnisse öffnen.',
    'nav_knowledge':'Die FAQ oder Hilfe öffnen.',
    'nav_voice':'Die eigene Stimme aufnehmen oder Stimmenverwaltung öffnen.',
    'machine_guard_open':'Die Schutzhaube oder Schutzklappe öffnen; Aufforderung oder Meldung, dass sie geöffnet wurde.',
    'machine_close_start':'Kombinierter Befehl: zuerst die Schutzhaube oder Schutzklappe schließen UND anschließend die Prüfung starten, z.B. schließe die Schutzhaube und starte die Prüfung.',
    'machine_abort':'Die laufende oder pausierte Prüfung abbrechen, stoppen oder beenden. Nicht nur pausieren.',
    'machine_guard_close':'Nur die Schutzhaube oder Schutzklappe schließen, ohne Startauftrag; Aufforderung oder Meldung, dass sie geschlossen wurde.',
    'machine_insert':'Das Ventil einlegen oder bestätigen, dass es bereits eingelegt ist, z.B. ich habe das Ventil eingelegt. Keine Frage nach einer Anleitung.',
    'machine_remove':'Das Ventil entnehmen oder melden, dass es entnommen wurde.',
    'machine_start':'Die simulierte Druckprüfung jetzt starten.',
    'machine_pause':'Die laufende Prüfung pausieren oder fortsetzen.',
    'machine_reset':'Die simulierte Prüfung zurücksetzen.',
    'protocol_summary':'Prüfstatistik abfragen: Anzahl abgeschlossener, bestandener oder fehlgeschlagener Prüfungen; Ausschuss, Fehlerquote oder letztes Prüfergebnis.',
    'machine_status':'Den aktuellen Zustand des Prüfstands, der Schutzhaube oder des eingelegten Ventils abfragen.',
    'machine_pressure':'Den aktuellen Druck des Prüfstands abfragen.',
    'fallback':'Kein passender Befehl und keine passende FAQ-Frage; unklar oder themenfremd.',
}


def machine_command(text):
    text=text.casefold().replace('ä','ae').replace('ö','oe').replace('ü','ue')
    vocabulary=['schutzhaube','schutzklappe','eingeliegt','eingelegt']
    def repair(match):
        token=match.group();near=difflib.get_close_matches(token,vocabulary,n=1,cutoff=.78)
        return near[0] if near else token
    text=re.sub(r'\b\w+\b',repair,text).replace('eingeliegt','eingelegt')
    if re.search(r'\b(wie ?viele|anzahl|bilanz|statistik|fehlerquote|ausschuss|fehlgeschlagen|durchgefallen)\b',text) and re.search(r'pruef|protokoll|ausschuss',text):return 'protocol_summary'
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
    aliases={'lange':'dauer','dauert':'dauer','dauern':'dauer','braucht':'dauer','zeit':'dauer','test':'pruefung','pruefzyklus':'pruefung','ablauf':'verfahren','funktioniert':'verfahren','methode':'verfahren','schutzhaube':'haube','schutzklappe':'haube','geschlossen':'schliessen','schliesse':'schliessen','pruefdruck':'druck','ergebnisse':'ergebnis','protokolle':'ergebnis','undicht':'leck','leckage':'leck','anhalten':'pause','pausieren':'pause','starte':'start','starten':'start'}
    return {aliases.get(word,word) for word in re.findall(r'\w+',text) if word not in stop}


def relevant_faq(text):
    query=faq_terms(text)
    with db() as c:catalog=[dict(row) for row in c.execute('SELECT id,question,answer FROM faq')]
    for row in catalog:
        terms=faq_terms(row['question'])
        overlap=query&terms
        row['match']=2*len(overlap)/max(1,len(query)+len(terms)) if overlap-{'pruefung','ventil'} else 0
    return sorted(catalog,key=lambda row:row['match'],reverse=True)


def decide(text, context=None, history=None):
    command=machine_command(text)
    if command:return command
    if re.fullmatch(r'\s*(hallo|hi|hey|guten (morgen|tag|abend)|moin|servus|tschuess)[!. ]*',text.casefold()):return 'greeting'
    # Actions and knowledge never compete in the same choice list.
    matches=relevant_faq(text)
    if matches and matches[0]['match']>=.78:return matches[0]['id']
    if agent is None:return 'fallback'
    knowledge=bool(re.search(r'\b(wie|warum|wann|wieso|weshalb)\b|\b(kann|darf|soll|muss) ich\b',text.casefold()))
    if not knowledge:
        criteria={k:v for k,v in ACTIONS.items() if k not in {'greeting','fallback'}}
        criteria['none']='Keine konkrete Aktion: Wissensfrage, allgemeine Unterhaltung oder unklarer Text.'
        with _lock:
            prediction=agent.predict(text,{'action':{'type':'choice','instructions':'Erkenne den gewünschten Auftrag sinngemäß. Keine Aktion bei Fragen nach einer Anleitung, Verneinung oder Unterhaltung. Dann none.','criteria':criteria}},lang='de')
        result=prediction.get('answers',prediction)['action'];probabilities=result.get('probabilities',{})
        ranked=sorted(probabilities.values(),reverse=True)
        if result['choice']!='none' and probabilities.get(result['choice'],0)>=.72 and (len(ranked)<2 or ranked[0]-ranked[1]>=.18):return result['choice']
    with db() as c:faqs=c.execute('SELECT * FROM faq').fetchall()
    criteria={r['id']:r['question']+' '+r['answer'] for r in faqs}
    criteria['none']='Keine dieser FAQ beantwortet die Frage; allgemeine Unterhaltung, unklarer Text oder anderes Thema.'
    with _lock:
        result=agent.predict(text,{'faq':{'type':'choice','instructions':'Wähle eine FAQ nur, wenn sie die konkrete Frage beantwortet. Erfinde keinen Zusammenhang. Sonst none.','criteria':criteria}},lang='de')
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
        if not record:raise RuntimeError('Die Antwortstimme ist nicht bereit.')
        opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
        models[voice_id]=PiperVoice(session=ort.InferenceSession(record['model'],sess_options=opts,providers=['CPUExecutionProvider']),config=PiperConfig.from_dict(json.loads(Path(record['config']).read_text())))
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:models[voice_id].synthesize_wav(text,wav)
    return output.getvalue()


class AnswerStream:
    def __init__(self,text,context,history):
        self.stopped=threading.Event();self.response=None
        self.messages=[{'role':'system','content':'Du bist Werkraum, ein deutscher Shopfloor-Assistent für Ventilprüfung, Haubensteuerung und Prüfprotokolle. Antworte sachlich in drei bis sechs kurzen Sätzen ohne Markdown. Nutze beigefügte Fakten; erfinde keine Messwerte oder ausgeführten Aktionen. Allgemeine Fragen sind erlaubt. Bei unklarem Text frage nach; benenne fehlendes Echtzeitwissen ehrlich.'},*history,{'role':'user','content':json.dumps({'question':text,'facts':context},ensure_ascii=False)}]
    def cancel(self):
        self.stopped.set()
        if self.response:
            # Closing the HTTP stream also cancels Ollama's remaining generation.
            try:self.response.close()
            except Exception:pass
    def sentences(self):
        payload={'model':os.getenv('QWEN_MODEL','qwen3.5:2b'),'stream':True,'think':False,'messages':self.messages,'options':{'num_predict':260,'num_ctx':2048,'num_gpu':0,'temperature':.35,'presence_penalty':0,'repeat_penalty':1.05,'num_thread':int(os.getenv('CPU_THREADS','4'))}}
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
            if not voice:raise RuntimeError('Die ausgewählte Stimme ist noch nicht bereit.')
            from piper import PiperVoice
            voices[voice_id]=PiperVoice.load(voice['model'],use_cuda=False)
        with wave.open(str(output),'wb') as wav:voices[voice_id].synthesize_wav(text,wav)


def transcribe(audio):
    if recognizer is None:raise RuntimeError('Die Spracherkennung wird noch vorbereitet.')
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
        segments,info=recognizer.transcribe(samples,language='de',beam_size=3,vad_filter=True,condition_on_previous_text=False,initial_prompt='Ventilprüfstand. Schutzhaube öffnen. Schutzhaube schließen. Ventil eingelegt. Prüfung starten, pausieren oder abbrechen. Prüfprotokolle. Fehlgeschlagene Prüfungen.')
        return ' '.join(s.text.strip() for s in segments).strip()


APPROVED_VARIANTS=json.loads((ROOT/'content/answer-variants.json').read_text())

class VariantsExhausted(Exception):
    pass

def approved_variants(category, base):
    if category.startswith('pressure:'):
        return [base, 'Der Messwert lautet: '+base.removeprefix('Der aktuelle Prüfdruck beträgt '), 'Aktuell werden '+base.removeprefix('Der aktuelle Prüfdruck beträgt ').removesuffix('.')+' angezeigt.']
    return [base, *APPROVED_VARIANTS.get(category, [])]

def paraphrase(text, existing, category):
    # Model output is an index into reviewed phrases, never playable free text.
    options=[v for v in approved_variants(category,text) if v not in existing]
    if not options:raise VariantsExhausted('Alle freigegebenen Formulierungen sind bereits im Cache.')
    return options[0]

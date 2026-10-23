"""CPU-only speech and typed decisions; model work stays outside the event loop."""
import io
import json
import os
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
    'machine_start':'Die simulierte Druckprüfung jetzt starten.',
    'machine_pause':'Die laufende Prüfung pausieren oder fortsetzen.',
    'machine_reset':'Die simulierte Prüfung zurücksetzen.',
    'machine_pressure':'Den aktuellen Druck des Prüfstands abfragen.',
    'fallback':'Kein passender Befehl und keine passende FAQ-Frage; unklar oder themenfremd.',
}


def decide(text):
    if agent is None:raise RuntimeError('Laya wird noch vorbereitet. Den Status findest du in der Verwaltung.')
    with db() as c:faqs=c.execute('SELECT * FROM faq').fetchall()
    criteria={**ACTIONS,**{r['id']:r['question'] for r in faqs}}
    with _lock:
        result=agent.predict(text,{'intent':{'type':'choice','instructions':'Wähle genau die passende Absicht. Wissensfragen zur Prüfung gehören zur FAQ. Befehle sind konkrete Aufforderungen. Unbekanntes gehört zu fallback.','criteria':criteria}},lang='de')
    answer=result.get('answers',result)['intent']
    choice=answer['choice']
    if choice not in criteria:raise RuntimeError('Ungültiges Laya-Ergebnis')
    return choice


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
    with _stt_lock:
        segments,info=recognizer.transcribe(io.BytesIO(audio),language='de',beam_size=1,vad_filter=True)
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
    base=os.getenv('OLLAMA_URL','http://127.0.0.1:11435')
    status['qwen']='working'
    try:
        r=request_json(base+'/api/chat',{
            'model':os.getenv('QWEN_MODEL','qwen3.5:2b'),'stream':False,'think':False,
            'format':{'type':'object','properties':{'index':{'type':'integer','enum':list(range(len(options)))}},'required':['index'],'additionalProperties':False},
            'messages':[{'role':'system','content':'Wähle eine kurze, natürliche Antwort aus der vorgegebenen Liste. Verändere keinen Text. Antworte ausschließlich mit dem JSON-Objekt mit dem gewählten Index.'},
                        {'role':'user','content':json.dumps({'answers':options},ensure_ascii=False)}],
            'options':{'num_predict':30,'temperature':.3,'num_ctx':2048,'num_gpu':0,'num_thread':int(os.getenv('CPU_THREADS','4'))}})
        index=json.loads(r['message']['content'])['index']
        if type(index) is not int or not 0<=index<len(options):raise RuntimeError('Ungültige Auswahl der Antwortvariante')
        status['qwen']='ready'
        return options[index]
    except Exception as e:
        status['qwen']='error: '+str(e)[:160]
        raise

"""Piper fine tuning jobs. Nothing is trained before the user starts the job."""
import asyncio
import importlib.util
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from uuid import uuid4
from .store import VAR, db

SENTENCES = [
'Die Prüfung ist abgeschlossen. Das Ventil ist dicht und kann entnommen werden.',
'Bitte schließe die Schutzhaube. Danach kann die Druckprüfung beginnen.',
'Der aktuelle Prüfdruck beträgt sechs bar. Die Messphase beginnt jetzt.',
'Das Ergebnis wurde gespeichert. Du findest es unter Prüfprotokolle.',
'Guten Morgen. Welchen Auftrag möchtest du heute bearbeiten?',
'Der Druckabfall liegt innerhalb des zulässigen Bereichs.',
'Die Prüfung wurde angehalten. Du kannst sie jederzeit fortsetzen.',
'Bitte prüfe die Anschlüsse und die Dichtung am Ventil.',
'Ich öffne die Übersicht der verfügbaren Prüfstände.',
'Dieses Bauteil muss nachgearbeitet und erneut geprüft werden.',
'Das Mikrofon ist bereit. Sprich in deiner natürlichen Lautstärke.',
'Es sind noch vier Bauteile bis zum Abschluss der Serie zu prüfen.',
'Der nächste Prüfauftrag gehört zur Ventilserie vierundzwanzig.',
'Die Schutzhaube ist geöffnet. Eine Prüfung kann so nicht starten.',
'Der Behälter ist leer. Bitte kontrolliere die Versorgung.',
'Wie kann ich dich bei der Arbeit am Prüfstand unterstützen?',
'Für diesen Auftrag sind hundert Bauteile vorgesehen.',
'Die Verbindung zum Arbeitsplatz wurde wiederhergestellt.',
'Das Ventil wird eingespannt und die Luftzufuhr vorbereitet.',
'Die gemessene Abweichung beträgt null Komma null zwei bar.',
'Der Bericht enthält die Ergebnisse der aktuellen Schicht.',
'Bitte bestätige, dass du diesen Vorgang beenden möchtest.',
'Es wurden keine weiteren Störungen am Prüfstand festgestellt.',
'Die Aufnahme klingt klar. Du kannst mit dem nächsten Satz fortfahren.',
'Dieses Gespräch bleibt gespeichert, bis du es selbst löschst.',
'Die Seriennummer steht auf der rechten Seite des Bauteils.',
'Die Prüfung beginnt nach dem vollständigen Druckaufbau.',
'Der Prüfstand wartet auf das nächste eingespannte Ventil.',
'Das aktuelle Programm ist für eine pneumatische Dichtheitsprüfung vorgesehen.',
'Vielen Dank. Ich wünsche dir eine ruhige und erfolgreiche Schicht.',
]


def prepare_training(voice_id):
    with db() as c:
        rows=c.execute('SELECT * FROM recording WHERE voice_id=?',(voice_id,)).fetchall()
        if len({r['text'] for r in rows})<20:raise ValueError('Für einen ersten Trainingslauf brauchst du mindestens 20 sauber gelesene Aufnahmen. Mehr Sprachmaterial verbessert das Ergebnis.')
        if not importlib.util.find_spec('piper.train'):raise ValueError('Die Piper-Trainingsabhängigkeiten sind nicht installiert.')
        pending=c.execute("SELECT id FROM job WHERE voice_id=? AND kind='training' AND state IN ('queued','running')",(voice_id,)).fetchone()
        if pending:return pending['id']
        jid=str(uuid4());c.execute("INSERT INTO job(id,kind,category,voice_id) VALUES(?,'training','voice',?)",(jid,voice_id));c.execute("UPDATE voice SET state='queued' WHERE id=?",(voice_id,))
    return jid


def run_training(job):
    vid=job['voice_id'];work=VAR/'training'/vid;work.mkdir(exist_ok=True);audio=work/'audio';audio.mkdir(exist_ok=True)
    with db() as c:rows=c.execute('SELECT * FROM recording WHERE voice_id=?',(vid,)).fetchall()
    lines=[]
    for r in rows:
        name=r['id']+'.wav';shutil.copyfile(r['path'],audio/name);lines.append(name+'|'+r['text'].replace('|',' ').replace('\n',' '))
    metadata=work/'metadata.csv';metadata.write_text('\n'.join(lines))
    checkpoint=VAR/'models/thorsten-medium.ckpt'
    if not checkpoint.exists():
        url='https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/de/de_DE/thorsten/medium/epoch%3D3135-step%3D2702056.ckpt'
        temp=checkpoint.with_suffix('.part')
        with urllib.request.urlopen(url,timeout=180) as source,temp.open('wb') as dest:
            while chunk:=source.read(1024*1024):dest.write(chunk)
        temp.replace(checkpoint)
    command=[sys.executable,'-m','piper.train','fit','--data.voice_name',vid,'--data.csv_path',str(metadata),'--data.audio_dir',str(audio),'--model.sample_rate','22050','--data.espeak_voice','de','--data.cache_dir',str(work/'cache'),'--data.config_path',str(work/'config.json'),'--data.batch_size','4','--model.warmstart_ckpt',str(checkpoint),'--trainer.accelerator','cpu','--trainer.devices','1','--trainer.max_epochs',os.getenv('TRAINING_EPOCHS','100'),'--trainer.default_root_dir',str(work)]
    with (work/'training.log').open('a') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        checkpoints=sorted(work.rglob('*.ckpt'),key=lambda p:p.stat().st_mtime)
        if not checkpoints:raise RuntimeError('Training hat keinen Checkpoint erzeugt.')
        out=VAR/'voices'/f'{vid}.onnx'
        subprocess.run([sys.executable,'-m','piper.train.export_onnx','--checkpoint',str(checkpoints[-1]),'--output-file',str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
    shutil.copyfile(work/'config.json',str(out)+'.json')
    with db() as c:c.execute("UPDATE voice SET state='ready',model=?,config=? WHERE id=?",(str(out),str(out)+'.json',vid))


async def worker():
    while True:
        with db() as c:
            row=c.execute("SELECT * FROM job WHERE kind='training' AND state='queued' ORDER BY created LIMIT 1").fetchone()
            job=dict(row) if row else None
            if job:c.execute("UPDATE job SET state='running' WHERE id=?",(job['id'],));c.execute("UPDATE voice SET state='training' WHERE id=?",(job['voice_id'],))
        if not job:await asyncio.sleep(1);continue
        try:
            await asyncio.to_thread(run_training,job)
            with db() as c:c.execute("UPDATE job SET state='done' WHERE id=?",(job['id'],))
        except Exception as e:
            with db() as c:
                c.execute("UPDATE job SET state='error',detail=? WHERE id=?",(str(e)[:500],job['id']))
                c.execute("UPDATE voice SET state='error' WHERE id=?",(job['voice_id'],))

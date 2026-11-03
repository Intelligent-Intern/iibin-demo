"""Piper fine tuning jobs. Nothing is trained before the user starts the job."""
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from uuid import uuid4
from .store import ROOT, VAR, db

SENTENCES = json.loads((ROOT/'content/sentences.json').read_text())


def prepare_training(voice_id):
    with db() as c:
        rows=c.execute('SELECT * FROM recording WHERE voice_id=?',(voice_id,)).fetchall()
        if len({r['text'] for r in rows})<20:raise ValueError('At least 20 clean recordings are required for an initial training run. More speech material improves the result.')
        if not importlib.util.find_spec('piper.train'):raise ValueError('Piper training dependencies are not installed.')
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
    checkpoint=VAR/'models/lessac-medium.ckpt'
    if not checkpoint.exists():
        url='https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/en/en_US/lessac/medium/epoch%3D2164-step%3D1355540.ckpt'
        temp=checkpoint.with_suffix('.part')
        with urllib.request.urlopen(url,timeout=180) as source,temp.open('wb') as dest:
            while chunk:=source.read(1024*1024):dest.write(chunk)
        temp.replace(checkpoint)
    command=[sys.executable,'-m','piper.train','fit','--data.voice_name',vid,'--data.csv_path',str(metadata),'--data.audio_dir',str(audio),'--model.sample_rate','22050','--data.espeak_voice','en-us','--data.cache_dir',str(work/'cache'),'--data.config_path',str(work/'config.json'),'--data.batch_size','4','--model.warmstart_ckpt',str(checkpoint),'--trainer.accelerator','cpu','--trainer.devices','1','--trainer.max_epochs',os.getenv('TRAINING_EPOCHS','100'),'--trainer.default_root_dir',str(work)]
    with (work/'training.log').open('a') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        checkpoints=sorted(work.rglob('*.ckpt'),key=lambda p:p.stat().st_mtime)
        if not checkpoints:raise RuntimeError('Training did not produce a checkpoint.')
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

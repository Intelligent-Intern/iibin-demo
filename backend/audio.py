import asyncio
import json
import sqlite3
import threading
from collections import defaultdict
from uuid import uuid4
from . import inference
from .store import VAR, db

BASE = {
'greeting':'Hallo! Ich unterstütze dich bei der Ventilprüfung. Was möchtest du wissen oder tun?',
'fallback':'Ich kann dir bei der Ventilprüfung helfen, Fragen zum Prüfablauf beantworten und Prüfprotokolle öffnen. Was möchtest du tun?',
'nav_machine':'Ich öffne die Ventilprüfung.', 'nav_dashboard':'Hier ist die Übersicht.',
'nav_protocols':'Ich öffne die Prüfprotokolle.', 'nav_knowledge':'Ich öffne die Fragen und Antworten.',
'nav_voice':'Ich öffne die Stimmenverwaltung.',
'machine_start':'Ich übergebe den Startbefehl an den simulierten Prüfstand.',
'machine_pause':'Ich übergebe den Befehl zum Pausieren oder Fortsetzen an den simulierten Prüfstand.',
'machine_reset':'Ich setze die simulierte Prüfung zurück.',
'machine_pressure':'Der aktuelle Prüfdruck wird in der Maschinenansicht angezeigt.',
}


def canonical(category):
    if category in BASE:return BASE[category]
    if category.startswith('pressure:'):
        return 'Der aktuelle Prüfdruck beträgt '+format(float(category.split(':',1)[1]),'.2f').replace('.',',')+' bar.'
    with db() as c:r=c.execute('SELECT answer FROM faq WHERE id=?',(category,)).fetchone()
    if not r:raise ValueError('Unbekannte Antwortkategorie')
    return r['answer']


def active_voice():
    with db() as c:return c.execute("SELECT value FROM setting WHERE key='active_voice'").fetchone()['value']


def enqueue(category,voice,kind='variant'):
    with db() as c:
        c.execute('INSERT OR IGNORE INTO job(id,kind,category,voice_id) VALUES(?,?,?,?)',(str(uuid4()),kind,category,voice))


def choose(tid,category,voice):
    with db() as c:
        r=c.execute('''SELECT v.* FROM answer_variant v WHERE category=? AND voice_id=?
        AND NOT EXISTS(SELECT 1 FROM playback p WHERE p.thread_id=? AND p.variant_id=v.id)
        ORDER BY created,id LIMIT 1''',(category,voice,tid)).fetchone()
        if not r:
            # Exhausting the reviewed wording pool must not leave voice mode silent.
            r=c.execute('''SELECT v.* FROM answer_variant v JOIN playback p ON p.variant_id=v.id
            WHERE v.category=? AND v.voice_id=? AND p.thread_id=? ORDER BY p.created,v.id LIMIT 1''',(category,voice,tid)).fetchone()
        return dict(r) if r else None


_creation_locks = defaultdict(threading.Lock)

def create_variant(category,voice,variation=False,base_text=None):
    with _creation_locks[(category,voice)]:
        return _create_variant(category,voice,variation,base_text)

def _create_variant(category,voice,variation=False,base_text=None):
    base=base_text if base_text is not None else canonical(category)
    with db() as c:existing=[r['text'] for r in c.execute('SELECT text FROM answer_variant WHERE category=? AND voice_id=?',(category,voice))]
    text=inference.paraphrase(base,existing,category) if variation else base
    if text in existing:
        if variation:raise RuntimeError('Das Modell hat eine vorhandene Variante wiederholt.')
        with db() as c:return dict(c.execute('SELECT * FROM answer_variant WHERE category=? AND voice_id=? AND text=?',(category,voice,text)).fetchone())
    vid=str(uuid4());path=VAR/'audio'/f'{vid}.wav'
    inference.synthesize(text,voice,path)
    try:
        with db() as c:c.execute('INSERT INTO answer_variant(id,category,voice_id,text,path) VALUES(?,?,?,?,?)',(vid,category,voice,text,str(path)))
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {'id':vid,'category':category,'voice_id':voice,'text':text,'path':str(path)}


def acknowledge(tid,variant):
    with db() as c:
        v=c.execute('SELECT * FROM answer_variant WHERE id=?',(variant,)).fetchone()
        if not v:raise ValueError('Unbekannte Audiodatei')
        c.execute('INSERT INTO playback(thread_id,variant_id) VALUES(?,?) ON CONFLICT(thread_id,variant_id) DO UPDATE SET created=CURRENT_TIMESTAMP',(tid,variant))
    enqueue(v['category'],v['voice_id'])


async def worker():
    while True:
        job=None
        with db() as c:
            row=c.execute("SELECT * FROM job WHERE state='queued' AND kind IN ('variant','initial') AND (kind='initial' OR ?) ORDER BY CASE kind WHEN 'initial' THEN 0 ELSE 1 END,created,id LIMIT 1",(inference.status['qwen'] in ('ready','working'),)).fetchone()
            if row:
                job=dict(row);c.execute("UPDATE job SET state='running' WHERE id=?",(job['id'],))
        if not job:
            await asyncio.sleep(.5);continue
        try:
            await asyncio.to_thread(create_variant,job['category'],job['voice_id'],job['kind']=='variant')
            with db() as c:
                c.execute("UPDATE job SET state='done',detail='' WHERE id=?",(job['id'],))
                count=c.execute('SELECT COUNT(*) FROM answer_variant WHERE category=? AND voice_id=?',(job['category'],job['voice_id'])).fetchone()[0]
            if count<3:enqueue(job['category'],job['voice_id'])
        except inference.VariantsExhausted as e:
            with db() as c:c.execute("UPDATE job SET state='done',detail=? WHERE id=?",(str(e),job['id']))
        except Exception as e:
            with db() as c:c.execute("UPDATE job SET state='error',detail=? WHERE id=?",(str(e)[:400],job['id']))


async def seed_cache():
    while inference.status['piper']=='loading':await asyncio.sleep(.5)
    if inference.status['piper']!='ready':return
    with db() as c:categories=list(BASE)+[r['id'] for r in c.execute('SELECT id FROM faq')]
    for category in categories:
        with db() as c:present=c.execute('SELECT 1 FROM answer_variant WHERE category=? AND voice_id=?',(category,'thorsten')).fetchone()
        if not present:enqueue(category,'thorsten','initial')

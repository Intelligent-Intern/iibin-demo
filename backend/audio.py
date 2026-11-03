import asyncio
import json
import sqlite3
import threading
from collections import defaultdict
from uuid import uuid4
from . import inference
from .store import VAR, db

BASE = {'greeting': 'Hello! I can help you with valve testing. What would you like to know or do?', 'fallback': 'I can help with valve testing, answer questions about the procedure and open inspection reports. What would you like to do?', 'nav_machine': 'Opening the valve test bench.', 'nav_dashboard': 'Here is the overview.', 'nav_protocols': 'Opening inspection reports.', 'nav_knowledge': 'Opening questions and answers.', 'nav_voice': 'Opening voice management.', 'machine_close_start': 'Closing the safety guard and starting the test.', 'machine_abort': 'Aborting the test.', 'machine_not_running': 'No test is currently running.', 'machine_guard_open': 'Sending the command to open the safety guard.', 'machine_guard_close': 'Sending the command to close the safety guard.', 'machine_insert': 'Noted: the valve has been inserted.', 'machine_remove': 'Noted: the valve has been removed.', 'machine_blocked_guard': 'Open the safety guard before inserting or removing the valve.', 'machine_blocked_start_guard': 'Close the safety guard first.', 'machine_blocked_valve': 'Insert a valve before starting the test.', 'machine_blocked_running': 'The test is still running. The safety guard and valve remain locked during the test.', 'machine_start': 'Sending the start command to the simulated test bench.', 'machine_pause': 'Sending the pause or resume command to the simulated test bench.', 'machine_reset': 'Resetting the simulated test.', 'machine_pressure': 'The machine view shows the current test pressure.'}


def canonical(category):
    if category in BASE:return BASE[category]
    if category.startswith('pressure:'):
        return 'The current test pressure is '+format(float(category.split(':',1)[1]),'.2f')+' bar.'
    with db() as c:r=c.execute('SELECT answer FROM faq WHERE id=?',(category,)).fetchone()
    if not r:raise ValueError('Unknown response category')
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
        if variation:raise RuntimeError('The model repeated an existing variant.')
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
        if not v:raise ValueError('Unknown audio file')
        c.execute('INSERT INTO playback(thread_id,variant_id) VALUES(?,?) ON CONFLICT(thread_id,variant_id) DO UPDATE SET created=CURRENT_TIMESTAMP',(tid,variant))
    with db() as c:known=c.execute('SELECT 1 FROM faq WHERE id=?',(v['category'],)).fetchone()
    if v['category'] in BASE or known or v['category'].startswith('pressure:'):enqueue(v['category'],v['voice_id'])


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
        with db() as c:present=c.execute('SELECT 1 FROM answer_variant WHERE category=? AND voice_id=?',(category,'lessac')).fetchone()
        if not present:enqueue(category,'lessac','initial')

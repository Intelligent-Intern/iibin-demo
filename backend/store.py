import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
VAR = Path(os.environ.get('IIBIN_DATA', ROOT / 'var'))
VAR.mkdir(parents=True, exist_ok=True)
for folder in ['audio','recordings','voices','models','training']:
    (VAR / folder).mkdir(exist_ok=True)

@contextmanager
def db():
    conn = sqlite3.connect(VAR / 'shopfloor.sqlite', timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

def init():
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS thread(id TEXT PRIMARY KEY,title TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS message(id TEXT PRIMARY KEY,thread_id TEXT NOT NULL REFERENCES thread(id) ON DELETE CASCADE,role TEXT NOT NULL,text TEXT NOT NULL,category TEXT,audio_id TEXT,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS message_thread ON message(thread_id,created);
        CREATE TABLE IF NOT EXISTS faq(id TEXT PRIMARY KEY,question TEXT NOT NULL,answer TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS voice(id TEXT PRIMARY KEY,name TEXT NOT NULL,state TEXT NOT NULL,model TEXT NOT NULL DEFAULT '',config TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS answer_variant(id TEXT PRIMARY KEY,category TEXT NOT NULL,voice_id TEXT NOT NULL REFERENCES voice(id),text TEXT NOT NULL,path TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(category,voice_id,text));
        CREATE INDEX IF NOT EXISTS variant_category ON answer_variant(category,voice_id);
        CREATE TABLE IF NOT EXISTS playback(thread_id TEXT NOT NULL REFERENCES thread(id) ON DELETE CASCADE,variant_id TEXT NOT NULL REFERENCES answer_variant(id) ON DELETE CASCADE,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(thread_id,variant_id));
        CREATE TABLE IF NOT EXISTS job(id TEXT PRIMARY KEY,kind TEXT NOT NULL,category TEXT NOT NULL,voice_id TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',detail TEXT NOT NULL DEFAULT '',created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE UNIQUE INDEX IF NOT EXISTS job_pending ON job(kind,category,voice_id) WHERE state IN ('queued','running');
        CREATE TABLE IF NOT EXISTS recording(id TEXT PRIMARY KEY,voice_id TEXT NOT NULL REFERENCES voice(id),text TEXT NOT NULL,path TEXT NOT NULL,duration REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS protocol(id TEXT PRIMARY KEY,pressure REAL NOT NULL,drop_value REAL NOT NULL,passed INTEGER NOT NULL,duration REAL NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS setting(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        for f in json.loads((ROOT/'content/faq.json').read_text()):
            c.execute('INSERT INTO faq VALUES(:id,:question,:answer) ON CONFLICT(id) DO UPDATE SET question=excluded.question,answer=excluded.answer',f)
        c.execute("INSERT OR IGNORE INTO voice(id,name,state) VALUES('lessac','Lessac','not_installed')")
        c.execute("INSERT OR IGNORE INTO setting VALUES('active_voice','lessac')")
        c.execute("UPDATE setting SET value='lessac' WHERE key='active_voice' AND value='thorsten'")
        c.execute("UPDATE job SET state='queued' WHERE state='running'")

def new_thread():
    tid=str(uuid4())
    with db() as c:c.execute('INSERT INTO thread(id,title) VALUES(?,?)',(tid,'New conversation'))
    return tid

def delete_thread(tid):
    with db() as c:c.execute('DELETE FROM thread WHERE id=?',(tid,))

def add_message(tid,role,text,category='',audio_id=''):
    mid=str(uuid4())
    with db() as c:
        c.execute('INSERT INTO message(id,thread_id,role,text,category,audio_id) VALUES(?,?,?,?,?,?)',(mid,tid,role,text,category,audio_id))
        if role=='user':c.execute("UPDATE thread SET title=? WHERE id=? AND title='New conversation'",(text[:55],tid))
    return mid

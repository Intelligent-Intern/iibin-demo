"""Immutable client-computed experiment records over the existing binary bus."""
import json, math
from uuid import uuid4
from .store import db
MODES={'moon','plasma','tribo','harvester','emitter','discharge','system'}
MAX_SAMPLES=3100

def init():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS lunar_experiment(
            id TEXT PRIMARY KEY,title TEXT NOT NULL,mode TEXT NOT NULL,model_version TEXT NOT NULL,
            payload TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')

def finite(value):
    if isinstance(value,float) and not math.isfinite(value): raise ValueError('Non-finite value in experiment.')
    if isinstance(value,dict):
        for child in value.values(): finite(child)
    if isinstance(value,list):
        for child in value: finite(child)

def validate(rows):
    if not isinstance(rows,list) or not 3<=len(rows)<=MAX_SAMPLES+1:raise ValueError('An experiment requires 2 to 3100 samples.')
    head=rows[0]
    if head.get('kind') not in MODES or not isinstance(head.get('text'),str):raise ValueError('Invalid experiment header.')
    try: metadata=json.loads(head['text'],parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite value.')))
    except (TypeError,json.JSONDecodeError) as error:raise ValueError('Invalid experiment metadata.') from error
    if (not isinstance(metadata,dict) or metadata.get('mode')!=head['kind'] or metadata.get('modelVersion')!='lcc-1.0.1'
        or not all(isinstance(metadata.get(key),dict) for key in ('parameters','ledger','flows','summary'))):raise ValueError('Invalid model version or experiment structure.')
    finite(metadata)
    previous=-1;last=None
    for row in rows[1:]:
        if row.get('kind')!='sample' or not isinstance(row.get('values'),list):raise ValueError('Invalid sample.')
        sample={}
        for v in row['values']:
            key=v.get('key');fields=[k for k in ('number','flag','text') if k in v]
            if not isinstance(key,str) or len(key)>80 or key in sample or len(fields)!=1:raise ValueError('Invalid measurement.')
            sample[key]=v[fields[0]]
        finite(sample);time=sample.get('time')
        if not isinstance(time,(int,float)) or not previous<time<=3600 or previous==-1 and time!=0:raise ValueError('Sample times must start at zero and increase strictly.')
        for field in ('voltage','charge','storage','energyResidual','chargeResidual'):
            if not isinstance(sample.get(field),(int,float)):raise ValueError('A required measurement is missing.')
        previous=time;last=sample
    if any(last.get(k)!=v for k,v in metadata['summary'].items() if v is not None):raise ValueError('Summary and final sample do not match.')
    payload=json.dumps(rows,allow_nan=False,separators=(',',':'))
    if len(payload)>8*1024*1024:raise ValueError('Experiment exceeds 8 MB.')
    return metadata,payload

def handle(op,packet):
    if op=='lunar.runs.save':
        rows=packet.get('rows');metadata,payload=validate(rows);identifier=str(uuid4())
        title=(rows[0].get('title') or 'Experiment').strip()[:160]
        with db() as c:c.execute('INSERT INTO lunar_experiment(id,title,mode,model_version,payload) VALUES(?,?,?,?,?)',(identifier,title,metadata['mode'],metadata['modelVersion'],payload))
        return {'rows':[{'id':identifier,'title':title,'kind':metadata['mode']}]}
    if op=='lunar.runs.list':
        with db() as c:return {'rows':[{'id':r['id'],'title':r['title'],'kind':r['mode'],'state':r['model_version'],'created':r['created']} for r in c.execute('SELECT id,title,mode,model_version,created FROM lunar_experiment ORDER BY created DESC,rowid DESC LIMIT 200')]}
    if op=='lunar.runs.get':
        with db() as c:r=c.execute('SELECT * FROM lunar_experiment WHERE id=?',(packet.get('tid',''),)).fetchone()
        if not r:raise ValueError('Experiment not found.')
        rows=json.loads(r['payload']);rows[0]['id']=r['id'];rows[0]['title']=r['title'];return {'rows':rows}
    if op=='lunar.runs.delete':
        with db() as c:c.execute('DELETE FROM lunar_experiment WHERE id=?',(packet.get('tid',''),))
        return {'state':'deleted'}
    raise ValueError('Unknown experiment operation.')

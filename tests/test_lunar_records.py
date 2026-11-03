import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import lunar,store
ROOT=Path(__file__).resolve().parents[1]
class Records(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script="""import {runExperiment} from './machines/simulation/lunar-charge-control/engine.js';const r=runExperiment('discharge',{duration:1});const {samples,...metadata}=r;console.log(JSON.stringify([{id:'configuration',kind:r.mode,title:'Referenzversuch',text:JSON.stringify(metadata)},...samples.map((s,i)=>({id:String(i),kind:'sample',values:Object.entries(s).filter(([,v])=>v!==null).map(([key,v])=>({key,[typeof v==='number'?'number':typeof v==='boolean'?'flag':'text']:v}))}))]));"""
        cls.rows=json.loads(subprocess.check_output(['node','--input-type=module','-e',script],cwd=ROOT))
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.patch=patch.object(store,'VAR',Path(self.temp.name));self.patch.start();self.addCleanup(self.patch.stop)
        store.init();lunar.init()
    def test_immutable_roundtrip_and_delete(self):
        saved=lunar.handle('lunar.runs.save',{'rows':self.rows})['rows'][0]
        listed=lunar.handle('lunar.runs.list',{})['rows'];self.assertEqual(listed[0]['id'],saved['id'])
        restored=lunar.handle('lunar.runs.get',{'tid':saved['id']})['rows']
        self.assertEqual(restored[1:],self.rows[1:]);self.assertEqual(restored[0]['text'],self.rows[0]['text'])
        lunar.handle('lunar.runs.delete',{'tid':saved['id']});self.assertEqual(lunar.handle('lunar.runs.list',{})['rows'],[])
    def test_bad_time_nonfinite_and_wrong_summary_are_rejected(self):
        for kind in ('time','nan','summary','version'):
            rows=copy.deepcopy(self.rows)
            if kind=='time':next(v for v in rows[2]['values'] if v['key']=='time')['number']=0
            if kind=='nan':next(v for v in rows[2]['values'] if v['key']=='voltage')['number']=float('nan')
            if kind in ('summary','version'):
                metadata=json.loads(rows[0]['text'])
                if kind=='summary':metadata['summary']['voltage']=123
                else:metadata['modelVersion']='unknown'
                rows[0]['text']=json.dumps(metadata)
            with self.assertRaises(ValueError):lunar.validate(rows)
if __name__=='__main__':unittest.main()

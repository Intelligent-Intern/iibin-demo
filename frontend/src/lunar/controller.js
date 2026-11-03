import {shallowRef,ref,onBeforeUnmount} from 'vue'
import {DEFAULTS,SCENARIOS,normalize,MODEL_VERSION} from '../../../machines/simulation/lunar-charge-control/parameters.js'
import {rpc,data} from '../transport'
export {DEFAULTS,SCENARIOS,normalize,MODEL_VERSION}
export const experimentSessions=new Map()
export function useExperiment(){
 const worker=new Worker(new URL('./simulation.worker.js',import.meta.url),{type:'module'})
 const snapshot=shallowRef(null),samples=shallowRef([]),running=ref(false),busy=ref(false),error=ref(''),speed=ref(5),result=shallowRef(null)
 let sequence=0,pending=new Map(),timer,accumulator=0,lastTime=0,mode,parameters,generation=0
 worker.onmessage=({data})=>{const p=pending.get(data.id);if(!p)return;pending.delete(data.id);data.error?p.reject(Error(data.error)):p.resolve(data)}
 worker.onerror=event=>{error.value=event.message||'Simulation worker unavailable.';running.value=false;for(const p of pending.values())p.reject(Error(error.value));pending.clear()}
 function request(op,values={}){const id=++sequence;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});worker.postMessage({id,op,...values})})}
 function apply(value){snapshot.value=value.state;samples.value=[...samples.value,...value.samples];if(value.result)result.value={...value.result,samples:samples.value};if(value.state.finished)running.value=false}
 async function reset(nextMode,nextParameters){running.value=false;busy.value=true;error.value='';accumulator=0;const current=++generation;try{mode=nextMode;parameters=normalize(nextParameters);samples.value=[];result.value=null;const response=await request('reset',{mode,parameters});if(current===generation)apply(response)}catch(e){error.value=e.message}finally{if(current===generation)busy.value=false}}
 async function step(seconds=.1){if(busy.value||!snapshot.value||snapshot.value.finished)return;busy.value=true;const current=generation;try{const response=await request('advance',{seconds,from:samples.value.length});if(current===generation)apply(response)}catch(e){error.value=e.message;running.value=false}finally{if(current===generation)busy.value=false}}
 function toggle(){if(!snapshot.value||snapshot.value.finished||busy.value)return;running.value=!running.value;lastTime=performance.now();accumulator=0}
 async function tick(){const now=performance.now();if(running.value&&!busy.value&&!document.hidden){accumulator+=Math.min(.1,(now-lastTime)/1000)*speed.value;const ticks=Math.min(2500,Math.floor((accumulator+1e-10)/.02));if(ticks){accumulator-=ticks*.02;await step(ticks*.02)}}lastTime=now}
 timer=setInterval(tick,40)
 onBeforeUnmount(()=>{clearInterval(timer);worker.terminate();for(const p of pending.values())p.reject(Error('View closed.'));pending.clear()})
 return {snapshot,samples,running,busy,error,speed,result,reset,step,toggle}
}
export function toValues(object){return Object.entries(object).filter(([,v])=>v!==null&&v!==undefined).map(([key,value])=>({key,[typeof value==='number'?'number':typeof value==='boolean'?'flag':'text']:value}))}
export async function saveRun(result,title){
 const {samples,...metadata}=result
 const rows=[{id:'configuration',kind:result.mode,title,text:JSON.stringify(metadata)},...samples.map((sample,index)=>({id:String(index),kind:'sample',values:toValues(sample)}))]
 const reply=await rpc('lunar.runs.save',{rows});return reply.rows[0]
}
export async function listRuns(){return (await rpc('lunar.runs.list')).rows||[]}
export async function loadRun(id){const reply=await rpc('lunar.runs.get',{tid:id}),[head,...rows]=reply.rows;return {...JSON.parse(head.text),title:head.title,id:head.id,samples:rows.map(data)}}
export function download(name,text,type='application/json'){
 const url=URL.createObjectURL(new Blob([text],{type})),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
export function exportCSV(run){const keys=Object.keys(run.samples[0]||{});const escape=v=>'"'+String(v??'').replaceAll('"','""')+'"';download(`lcc-${run.mode}-${Date.now()}.csv`,'# '+JSON.stringify({modelVersion:run.modelVersion,mode:run.mode,parameters:run.parameters,units:'SI: s,C,V,A,J,W',initialEnergy:run.initialEnergy,ledger:run.ledger,flows:run.flows})+'\r\n'+keys.join(',')+'\r\n'+run.samples.map(row=>keys.map(k=>escape(row[k])).join(',')).join('\r\n'),'text/csv;charset=utf-8')}

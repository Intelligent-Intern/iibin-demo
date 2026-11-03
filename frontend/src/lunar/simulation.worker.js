import {LunarSimulation} from '../../../machines/simulation/lunar-charge-control/engine.js'
let simulation
self.onmessage=({data})=>{
 try{
  if(data.op==='reset')simulation=new LunarSimulation(data.mode,data.parameters)
  else if(data.op==='advance'){if(!simulation)throw Error('No experiment active.');simulation.advance(data.seconds)}
  else throw Error('Unknown simulation command.')
  const samples=simulation.samples.slice(data.from||0)
  self.postMessage({id:data.id,state:simulation.snapshot(),samples,result:data.op==='reset'?null:{...simulation.result(),samples:undefined}})
 }catch(error){self.postMessage({id:data.id,error:error.message})}
}

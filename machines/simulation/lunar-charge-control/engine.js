import {normalize,MODEL_VERSION} from './parameters.js'
const E_CHARGE=1.602176634e-19
export const FIXED_STEP=.02
export function rcTransfer(voltage,target,capacitance,resistance,limit,dt){
 const d=voltage-target,sign=Math.sign(d),a=Math.abs(d),k=limit*resistance
 let remainder=dt,next=a
 if(a>k){const linear=Math.min(remainder,(a-k)*capacitance/limit);next-=linear*limit/capacitance;remainder-=linear}
 next*=Math.exp(-remainder/(resistance*capacitance))
 return {voltage:target+sign*next,charge:capacitance*(sign*next-d),released:.5*capacitance*(a*a-next*next)}
}
export class LunarSimulation{
 constructor(mode,input={}){
  if(!['moon','system','plasma','tribo','harvester','emitter','discharge'].includes(mode))throw Error('Unknown test bench.')
  this.mode=mode;this.p=normalize(input);const p=this.p
  this.c=(p.suitCapacitance+p.strayCapacitance)*1e-12
  this.q=p.initialMode==='charge'?p.initialCharge*1e-6:this.c*p.initialVoltage
  this.initialQ=this.q;this.storage=p.initialStorage
  this.internalC=p.inputCapacitance*1e-12
  this.internalQ=['harvester','moon','system'].includes(mode)&&!['tribo','plasma'].includes(p.harvester)?(p.inputMode==='charge'?p.inputCharge*1e-9:this.internalC*p.inputVoltage):0
  this.t=0;this.requestedTime=0;this.stepCount=0;this.emitterOn=false;this.dischargeAt=null;this.neutralizedAt=null
  this.ledger={plasmaWork:0,mechanicalWork:0,referenceWork:0,additionalWork:0,loss:0,loadEnergy:0,emitterEnergy:0,particleEnergy:0,harvested:0}
  this.flows={plasma:0,tribo:0,collector:0,emitter:0,lander:0,leak:0,additional:0}
  this.initialEnergy=this.fieldEnergy()+this.internalEnergy()+this.storage
  this.peakCurrent=0;this.peakVoltage=Math.abs(this.voltage());this.samples=[];this.lastSample=-Infinity
  this.samplePeriod=Math.max(.02,p.duration/3000);this.last={plasmaCurrent:0,triboCurrent:0,emitterCurrent:0,landerCurrent:0,collectorCurrent:0,plasmaPower:0,harvestPower:0,loadPower:0}
  this.record(true)
 }
 voltage(){return this.q/this.c}
 fieldEnergy(){return this.q*this.q/(2*this.c)}
 internalEnergy(){return this.internalQ*this.internalQ/(2*this.internalC)}
 environment(t=this.t){
  const p=this.p,eva=['moon','system'].includes(this.mode),f=t/p.duration
  const shadow=eva?f>=.38&&f<.65:!p.illuminated
  return {voltage:shadow?(eva?p.shadowVoltage:p.environmentVoltage):p.environmentVoltage,shadow,walking:eva?f<.75:this.mode==='tribo'||this.mode==='harvester'&&p.harvester==='tribo',contact:this.mode==='discharge'||eva&&f>=.75,phase:!eva?'Experiment':f<.18?'Leaving lander':f<.38?'Illuminated surface':f<.65?'Permanent shadow':f<.75?'Return':'Potential equalization'}
 }
 currents(q,env){
  const p=this.p,d=q/this.c-env.voltage
  const eva=['moon','system'].includes(this.mode)
  const electrons=-E_CHARGE*p.collectionArea*p.electronFlux*(env.shadow&&eva?p.shadowElectronFactor:1)*Math.exp(Math.max(-745,Math.min(0,d/p.electronEnergy)))
  const ions=E_CHARGE*p.collectionArea*p.ionFlux*(env.shadow&&eva?p.shadowIonFactor:1)*Math.exp(Math.max(-745,Math.min(0,-d/p.ionEnergy)))
  const photo=env.shadow?0:p.photoCurrent*1e-9*Math.exp(-Math.min(745,Math.max(0,d)/2))
  return electrons+ions+photo
 }
 chargeWork(dq,channel,work){
  const old=this.q;this.q+=dq;this.flows[channel]+=dq
  this.ledger[work]+=(old+this.q)/(2*this.c)*dq
 }
 plasma(dt,env){
  const p=this.p,old=this.q
  // Backward Euler: monotone current law -> unique, bracketed solution.
  const bound=dt*(E_CHARGE*p.collectionArea*(p.electronFlux*Math.max(1,p.shadowElectronFactor)+p.ionFlux*Math.max(1,p.shadowIonFactor))+p.photoCurrent*1e-9)
  let lo=old-bound,hi=old+bound
  for(let i=0;i<56;i++){const mid=(lo+hi)/2;if(mid-old-dt*this.currents(mid,env)>0)hi=mid;else lo=mid}
  const dq=(lo+hi)/2-old;this.chargeWork(dq,'plasma','plasmaWork');this.last.plasmaCurrent=dq/dt;this.last.plasmaPower=(old+this.q)/(2*this.c)*dq/dt
 }
 store(energy){
  if(energy<=0)return
  const accepted=Math.min(energy,Math.max(0,.5*this.p.storageCapacitance*this.p.storageMaxVoltage**2-this.storage))
  this.storage+=accepted;this.ledger.harvested+=accepted;this.ledger.loss+=energy-accepted
 }
 reference(dt,target,resistance,limit,channel,efficiency=0){
  const transfer=rcTransfer(this.voltage(),target,this.c,resistance,limit,dt)
  this.q+=transfer.charge;this.flows[channel]+=transfer.charge
  this.ledger.referenceWork+=target*transfer.charge
  this.store(transfer.released*efficiency);this.ledger.loss+=transfer.released*(1-efficiency)
  return transfer.charge/dt
 }
 contactStep(){
  const p=this.p,construction={insulating:1,multilayer:.65,electrodes:.5,generator:.65,optimized:.2}[p.sole]
  const material={polymer:1,composite:.75,conductive:.4}[p.contactMaterial]
  let dq=p.chargePerContact*1e-9*(p.contactArea/180)*Math.sqrt(p.contactForce/140)*p.coupling*p.regolithFactor*construction*material*(1-Math.exp(-p.contactTime/.1))*(1-Math.exp(-p.releaseTime/.05))
  const oldEnergy=this.fieldEnergy(),oldQ=this.q
  if(((oldQ+dq)**2-oldQ**2)/(2*this.c)>p.stepWork){
   let low=0,high=1
   for(let i=0;i<50;i++){const m=(low+high)/2;if(((oldQ+dq*m)**2-oldQ**2)/(2*this.c)>p.stepWork)high=m;else low=m}
   dq*=low
  }
  this.q+=dq;this.flows.tribo+=dq
  const fieldChange=this.fieldEnergy()-oldEnergy
  const generator=p.sole==='generator'||p.harvester==='tribo'
  const internalInput=generator?Math.min(Math.max(0,p.stepWork-Math.max(0,fieldChange)),p.stepWork*p.generatorFraction):0
  this.ledger.mechanicalWork+=p.stepWork
  this.ledger.loss+=Math.max(0,p.stepWork-fieldChange-internalInput)+internalInput*(1-p.efficiency)
  this.store(internalInput*p.efficiency);this.stepCount++
 }
 harvest(dt,env){
  const p=this.p,start=this.ledger.harvested
  if(p.harvester==='plasma')this.last.collectorCurrent=this.reference(dt,env.voltage,p.collectorResistance*1e6,Infinity,'collector',p.efficiency)
  else if(p.harvester==='capacitive'){
   const ci=this.internalC,cs=p.storageCapacitance,vi=this.internalQ/ci,vs=Math.sqrt(2*this.storage/cs),ceq=ci*cs/(ci+cs)
   const dq=ceq*(vi-vs)*(-Math.expm1(-dt/(p.collectorResistance*1e6*ceq)))
   const before=this.internalEnergy()+this.storage;this.internalQ-=dq;this.storage=.5*cs*(vs+dq/cs)**2
   this.ledger.loss+=Math.max(0,before-this.internalEnergy()-this.storage)
   const cap=.5*cs*p.storageMaxVoltage**2
   if(this.storage>cap){this.ledger.loss+=this.storage-cap;this.storage=cap}
   this.ledger.harvested+=Math.max(0,this.storage-.5*cs*vs*vs)
  }else if(p.harvester!=='tribo'){
   const floor=.5*this.internalC*p.busVoltage**2
   const available=Math.max(0,this.internalEnergy()-floor),draw=Math.min(available,p.conversionPower*1e-3*dt)
   this.internalQ=Math.sign(this.internalQ)*Math.sqrt(Math.max(0,this.internalQ*this.internalQ-2*this.internalC*draw))
   const efficiency=p.efficiency**(p.harvester==='multistage'?p.stages:1)
   this.store(draw*efficiency);this.ledger.loss+=draw*(1-efficiency)
  }
  this.last.harvestPower=(this.ledger.harvested-start)/dt
 }
 emitter(dt){
  const p=this.p,v=this.voltage()
  if(v<=p.emitterOnVoltage)this.emitterOn=true
  if(v>=p.emitterOffVoltage)this.emitterOn=false
  const failed=p.emitterFailureAt>=0&&this.t>=p.emitterFailureAt
  if(!p.emitterEnabled||!this.emitterOn||failed)return
  const energy=p.emitterPower*1e-3*dt,fraction=energy>0?Math.min(1,this.storage/energy):1
  const target=this.c*p.emitterOffVoltage
  const dq=Math.min(Math.max(0,target-this.q),p.emissionCurrent*1e-6*p.extractionEfficiency*p.escapeFraction*dt*fraction)
  const before=this.fieldEnergy();this.q+=dq;this.flows.emitter+=dq
  this.ledger.particleEnergy+=Math.max(0,before-this.fieldEnergy())
  this.storage-=energy*fraction;this.ledger.emitterEnergy+=energy*fraction;this.last.emitterCurrent=dq/dt
  if(this.voltage()>=p.emitterOffVoltage-1e-6&&this.neutralizedAt===null)this.neutralizedAt=this.t+dt
 }
 step(dt){
  const p=this.p,env=this.environment(this.t+dt/2),eva=['moon','system'].includes(this.mode)
  for(const key of Object.keys(this.last))this.last[key]=0
  if(this.mode==='plasma'||eva)this.plasma(dt,env)
  if(this.mode==='emitter'){this.chargeWork(p.additionalCurrent*1e-9*dt,'additional','additionalWork')}
  if(env.walking&&p.stepFrequency>0){
   const expected=Math.floor((this.t+dt+1e-10)*p.stepFrequency)
   while(this.stepCount<expected){const before=this.flows.tribo;this.contactStep();this.last.triboCurrent+=(this.flows.tribo-before)/dt}
   // Only an explicitly conductive contact has an external leakage path.
   if((p.sole==='optimized'||p.contactMaterial==='conductive')&&(this.t+dt/2)%(1/p.stepFrequency)<p.contactTime)this.reference(dt,env.voltage,p.soleResistance*1e9,Infinity,'leak')
  }
  if(this.mode==='harvester'||eva)this.harvest(dt,env)
  if(this.mode==='emitter'||eva)this.emitter(dt)
  const contactTime=this.mode==='discharge'?this.t:this.t-p.duration*.75
  if(env.contact&&(p.contactInterruptedAt<0||contactTime<p.contactInterruptedAt)){
   const initialCurrent=Math.min(Math.abs(this.voltage()-p.landerVoltage)/(p.dischargeResistance*1e6),p.currentLimit*1e-3)
   this.peakCurrent=Math.max(this.peakCurrent,initialCurrent)
   this.last.landerCurrent=this.reference(dt,p.landerVoltage,p.dischargeResistance*1e6,p.currentLimit*1e-3,'lander',p.recovery?p.efficiency:0)
   if(Math.abs(this.voltage()-p.landerVoltage)<=p.targetDelta&&this.dischargeAt===null)this.dischargeAt=contactTime+dt
  }
  const vstore=Math.sqrt(2*this.storage/p.storageCapacitance)
  const qstore=Math.max(0,p.storageCapacitance*vstore-p.leakageCurrent*1e-6*dt)
  const nextStorage=qstore*qstore/(2*p.storageCapacitance);this.ledger.loss+=this.storage-nextStorage;this.storage=nextStorage
  const consumed=Math.min(this.storage,p.loadPower*1e-3*dt);this.storage-=consumed;this.ledger.loadEnergy+=consumed;this.last.loadPower=consumed/dt
  this.t+=dt;this.peakVoltage=Math.max(this.peakVoltage,Math.abs(this.voltage()))
 }
 advance(seconds){
  if(typeof seconds!=='number'||!Number.isFinite(seconds)||seconds<0)throw Error('Invalid time interval.')
  let target=Math.min(this.p.duration,this.requestedTime+seconds)
  if(Math.abs(target-this.p.duration)<1e-9)target=this.p.duration
  this.requestedTime=target
  while(this.t<target-1e-12){
   let end=Math.min(this.p.duration,(Math.floor((this.t+1e-10)/FIXED_STEP)+1)*FIXED_STEP)
   if(this.p.stepFrequency>0)end=Math.min(end,(Math.floor((this.t+1e-9)*this.p.stepFrequency)+1)/this.p.stepFrequency)
   if(['moon','system'].includes(this.mode))for(const f of [.18,.38,.65,.75]){const at=f*this.p.duration;if(at>this.t+1e-9)end=Math.min(end,at)}
   for(const at of [this.p.emitterFailureAt,this.p.contactInterruptedAt<0?-1:this.p.contactInterruptedAt+(this.mode==='discharge'?0:this.p.duration*.75)])if(at>this.t+1e-9)end=Math.min(end,at)
   if(end>target+1e-10)break
   this.step(end-this.t);this.record()
  }
  if(this.t>=this.p.duration-1e-9)this.record(true)
  return this.snapshot()
 }
 snapshot(){
  const p=this.p,env=this.environment(),field=this.fieldEnergy(),internal=this.internalEnergy(),l=this.ledger
  const work=l.plasmaWork+l.mechanicalWork+l.referenceWork+l.additionalWork
  const out=l.loss+l.loadEnergy+l.emitterEnergy+l.particleEnergy
  const qsum=Object.values(this.flows).reduce((a,b)=>a+b,0)
  return {time:this.t,charge:this.q,voltage:this.voltage(),environmentVoltage:env.voltage,deltaVoltage:this.voltage()-p.landerVoltage,fieldEnergy:field,internalEnergy:internal,storage:this.storage,storageVoltage:Math.sqrt(2*this.storage/p.storageCapacitance),inputVoltage:this.internalQ/this.internalC,outputVoltage:this.storage>0||this.last.loadPower>0?p.outputVoltage:0,outputCurrent:this.last.loadPower/p.outputVoltage,harvested:l.harvested,loss:l.loss,consumed:l.loadEnergy+l.emitterEnergy,particleEnergy:l.particleEnergy,externalWork:work,energyResidual:field+internal+this.storage+out-this.initialEnergy-work,chargeResidual:this.q-this.initialQ-qsum,emittedCharge:this.flows.emitter,peakCurrent:this.peakCurrent,peakVoltage:this.peakVoltage,steps:this.stepCount,phase:env.phase,shadow:env.shadow,contact:env.contact,walking:env.walking,emitterOn:this.emitterOn&&p.emitterEnabled&&(p.emitterFailureAt<0||this.t<p.emitterFailureAt)&&this.storage>0,emitterFailed:p.emitterFailureAt>=0&&this.t>=p.emitterFailureAt,dischargeAt:this.dischargeAt,neutralizedAt:this.neutralizedAt,finished:this.t>=p.duration-1e-9,...this.last}
 }
 record(force=false){
  if(force||this.t-this.lastSample>=this.samplePeriod-1e-9){const value=this.snapshot();if(this.samples.at(-1)?.time===value.time)this.samples[this.samples.length-1]=value;else this.samples.push(value);this.lastSample=this.t}
 }
 result(){return {modelVersion:MODEL_VERSION,mode:this.mode,parameters:{...this.p},initialEnergy:this.initialEnergy,ledger:{...this.ledger},flows:{...this.flows},summary:this.snapshot(),samples:this.samples.map(s=>({...s}))}}
}
export function runExperiment(mode,parameters){const sim=new LunarSimulation(mode,parameters);sim.advance(sim.p.duration);return sim.result()}

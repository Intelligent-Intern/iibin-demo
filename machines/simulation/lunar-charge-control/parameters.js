// Display units are declared here; engine.js converts every quantity to SI.
export const MODEL_VERSION = 'lcc-1.0.1'
export const MODES = [
 {id:'moon',title:'Moon simulation',description:'Suit, lander and environment during an EVA.',symbol:'Orbit'},
 {id:'plasma',title:'Plasma test bench',description:'Electrons, ions and photoemission.',symbol:'Waves'},
 {id:'tribo',title:'Triboelectric test bench',description:'Sole contact, net charge and internal generation.',symbol:'Footprints'},
 {id:'harvester',title:'Energy harvester',description:'Reference nodes, charge paths and electrical storage.',symbol:'BatteryCharging'},
 {id:'emitter',title:'Electron emitter',description:'Control, escaping electrons and power demand.',symbol:'Radio'},
 {id:'discharge',title:'Discharge test bench',description:'Current-limited potential equalization at the lander.',symbol:'Cable'},
 {id:'system',title:'Integrated system',description:'Complete EVA sequence with a shared balance.',symbol:'Layers3'},
]
const all=MODES.map(m=>m.id),eva=['moon','system']
const p=(key,label,unit,value,min,max,step,modes,group,extra={})=>({key,label,unit,value,min,max,step,modes,group,...extra})
export const PARAMETERS=[
 p('duration','Experiment duration','s',120,.1,3600,.1,all,'Experiment'),
 p('suitCapacitance','Suit capacitance','pF',200,10,10000,10,all,'Suit'),
 p('initialVoltage','Initial potential','V',-100000,-1000000,1000000,100,all,'Suit'),
 p('initialCharge','Initial charge','µC',-20,-10000,10000,.1,all,'Suit'),
 p('initialMode','Initial condition','', 'voltage',0,0,0,all,'Suit',{options:{voltage:'Specify voltage',charge:'Specify charge'}}),
 p('strayCapacitance','Cable and contact capacitance','pF',0,0,10000,10,['discharge',...eva],'Suit'),
 p('initialStorage','Initial stored energy','J',5,0,10000,.1,all,'Storage'),
 p('storageCapacitance','Storage capacitance','F',1,.001,1000,.01,['harvester',...eva],'Storage'),
 p('outputVoltage','Regulated output voltage','V',3.3,.1,1000,.1,['harvester',...eva],'Storage'),
 p('storageMaxVoltage','Storage voltage limit','V',5,.1,1000,.1,['harvester',...eva],'Storage'),
 p('loadPower','Electrical load','mW',0,0,10000,.1,['harvester',...eva],'Storage'),
 p('collectionArea','Plasma collection area','m²',2,.01,20,.01,['plasma',...eva],'Plasma'),
 p('electronFlux','Electron flux','1/(m²·s)',1e11,0,1e15,1e9,['plasma',...eva],'Plasma'),
 p('ionFlux','Ion flux','1/(m²·s)',1e10,0,1e15,1e9,['plasma',...eva],'Plasma'),
 p('electronEnergy','Electron energy','eV',200,.1,100000,1,['plasma',...eva],'Plasma'),
 p('ionEnergy','Ion energy','eV',20,.1,100000,1,['plasma',...eva],'Plasma'),
 p('environmentVoltage','Environment potential','V',0,-100000,100000,10,['plasma','harvester','tribo',...eva],'Plasma'),
 p('illuminated','Illumination','',true,0,0,0,['plasma',...eva],'Plasma'),
 p('photoCurrent','Photoemission when illuminated','nA',30,0,100000,1,['plasma',...eva],'Plasma'),
 p('shadowVoltage','Shadow potential','V',-500,-100000,100000,10,eva,'EVA'),
 p('shadowElectronFactor','Electron flux in shadow','×',2,0,100,.1,eva,'EVA'),
 p('shadowIonFactor','Ion flux in shadow','×',.1,0,100,.1,eva,'EVA'),
 p('stepFrequency','Step frequency','Hz',1,0,5,.1,['tribo',...eva],'Sole'),
 p('contactArea','Contact area','cm²',180,1,1000,1,['tribo',...eva],'Sole'),
 p('contactForce','Contact force','N',140,0,3000,10,['tribo',...eva],'Sole'),
 p('contactTime','Contact time','s',.3,.01,5,.01,['tribo',...eva],'Sole'),
 p('releaseTime','Separation time','s',.15,.01,5,.01,['tribo',...eva],'Sole'),
 p('chargePerContact','Reference transfer per contact','nC',-.2,-1000,1000,.01,['tribo',...eva],'Sole'),
 p('coupling','Electrical coupling to suit','',.8,0,1,.01,['tribo',...eva],'Sole'),
 p('regolithFactor','Regolith transfer factor','',1,0,5,.1,['tribo',...eva],'Sole'),
 p('soleResistance','Leakage path to ground','GΩ',1000,.001,1e9,1,['tribo',...eva],'Sole'),
 p('stepWork','Mechanical work per step','J',.03,0,100,.001,['tribo',...eva],'Sole'),
 p('sole','Sole construction','', 'insulating',0,0,0,['tribo',...eva],'Sole',{options:{insulating:'Insulating sole',multilayer:'Multilayer sole',electrodes:'Integrated electrodes',generator:'Internal triboelectric generator',optimized:'Charge-optimized contact'}}),
 p('contactMaterial','Contact material','', 'polymer',0,0,0,['tribo',...eva],'Sole',{options:{polymer:'Polymer / Regolith',composite:'Composite / regolith',conductive:'Conductive contact / regolith'}}),
 p('harvester','Harvester concept','', 'isolated',0,0,0,['harvester',...eva],'Harvester',{options:{isolated:'Isolated HV converter',capacitive:'Internal capacitive charge sharing',multistage:'Multistage isolated converter',tribo:'Internal triboelectric generator',plasma:'Collector with second reference node'}}),
 p('inputMode','Internal input condition','', 'voltage',0,0,0,['harvester',...eva],'Harvester',{options:{voltage:'Input voltage',charge:'Input charge'}}),
 p('inputCharge','Internal input charge','nC',1000,0,1e9,10,['harvester',...eva],'Harvester'),
 p('inputVoltage','Internal input voltage','V',10000,0,1000000,100,['harvester',...eva],'Harvester'),
 p('inputCapacitance','Internal input capacitance','pF',100,1,1000000,10,['harvester',...eva],'Harvester'),
 p('efficiency','Converter efficiency','',.65,0,1,.01,['harvester','tribo','discharge',...eva],'Harvester'),
 p('conversionPower','Maximum input power','mW',1,0,10000,.1,['harvester',...eva],'Harvester'),
 p('leakageCurrent','Storage leakage current','µA',.1,0,10000,.1,['harvester',...eva],'Storage'),
 p('busVoltage','DC link voltage','V',48,.1,10000,1,['harvester',...eva],'Harvester'),
 p('stages','Converter stages','',3,1,10,1,['harvester',...eva],'Harvester'),
 p('collectorResistance','Transfer / collector resistance','MΩ',10000,1,10000000,10,['harvester',...eva],'Harvester'),
 p('generatorFraction','Generator share of step work','',.1,0,1,.01,['tribo','harvester',...eva],'Harvester'),
 p('emissionCurrent','Emission current','µA',.5,0,100,.01,['emitter',...eva],'Emitter'),
 p('extractionEfficiency','Extraction efficiency','',.8,0,1,.01,['emitter',...eva],'Emitter'),
 p('escapeFraction','Escaping electron fraction','',.7,0,1,.01,['emitter',...eva],'Emitter'),
 p('emitterPower','Electrical power demand','mW',20,0,10000,1,['emitter',...eva],'Emitter'),
 p('emitterOnVoltage','Activation threshold','V',-2000,-1000000,-1,100,['emitter',...eva],'Emitter'),
 p('emitterOffVoltage','Deactivation threshold','V',-500,-1000000,0,100,['emitter',...eva],'Emitter'),
 p('additionalCurrent','Additional external charging current','nA',-1,-10000,10000,.1,['emitter'],'Emitter'),
 p('emitterEnabled','Emitter enabled','',true,0,0,0,['emitter',...eva],'Emitter'),
 p('emitterFailureAt','Emitter failure at (−1: disabled)','s',-1,-1,3600,1,['emitter',...eva],'Faults'),
 p('landerVoltage','Lander potential','V',100,-10000,10000,10,['discharge',...eva],'Discharge'),
 p('dischargeResistance','Discharge resistance','MΩ',600,1,1000000,1,['discharge',...eva],'Discharge'),
 p('currentLimit','Current limit','mA',.2,.001,10,.01,['discharge',...eva],'Discharge'),
 p('recovery','Energy recovery','',false,0,0,0,['discharge',...eva],'Discharge'),
 p('contactInterruptedAt','Contact interruption at (−1: disabled)','s',-1,-1,3600,.1,['discharge',...eva],'Faults'),
 p('targetDelta','Target voltage difference','V',10,.1,1000,1,['discharge',...eva],'Discharge'),
 p('systemMass','System mass','kg',4,.1,100,.1,['discharge',...eva],'Discharge'),
]
export const DEFAULTS=Object.fromEntries(PARAMETERS.map(p=>[p.key,p.value]))
export function normalize(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('A parameter set must be an object.')
 const result={...DEFAULTS}
 for(const [key,value]of Object.entries(input)){
  const def=PARAMETERS.find(p=>p.key===key)
  if(!def)throw Error(`Unknown parameter: ${key}`)
  if(def.options){if(!Object.hasOwn(def.options,value))throw Error(`Invalid selection: ${def.label}`)}
  else if(typeof def.value==='boolean'){if(typeof value!=='boolean')throw Error(`Invalid switch: ${def.label}`)}
  else if(typeof value!=='number'||!Number.isFinite(value)||value<def.min||value>def.max)throw Error(`Outside allowed range: ${def.label}`)
  result[key]=value
 }
 if(!Number.isInteger(result.stages))throw Error('Converter stages must be integers.')
 if(result.emitterOffVoltage<=result.emitterOnVoltage)throw Error('The deactivation threshold must exceed the activation threshold.')
 if(result.contactTime+result.releaseTime>1/Math.max(result.stepFrequency,1e-9))throw Error('Contact and separation times exceed the step period.')
 if(result.inputMode==='charge'&&result.inputCharge*1e-9/(result.inputCapacitance*1e-12)>1e6)throw Error('Internal input voltage exceeds 1 MV.');
 if(result.initialStorage>.5*result.storageCapacitance*result.storageMaxVoltage**2)throw Error('Initial energy exceeds storage capacity.')
 return result
}
export const SCENARIOS={
 moon:[{name:'EVA: light → shadow → lander',values:{duration:120,initialVoltage:-10000,dischargeResistance:300}}],
 system:[{name:'EVA with neutralization',values:{duration:120,initialVoltage:-10000,dischargeResistance:300}},{name:'EVA without emitter',values:{duration:120,initialVoltage:-10000,emitterEnabled:false,dischargeResistance:300}}],
 plasma:[{name:'Illuminated surface',values:{initialVoltage:0,duration:60}},{name:'Permanent shadow',values:{initialVoltage:0,illuminated:false,environmentVoltage:-500,ionFlux:1e9,electronFlux:2e11,duration:60}}],
 tribo:[{name:'Reference insulating sole',values:{initialVoltage:0,duration:30,sole:'insulating'}},{name:'Internal generator',values:{initialVoltage:0,duration:30,sole:'generator',harvester:'tribo'}},{name:'Charge-optimized contact',values:{initialVoltage:0,duration:30,sole:'optimized'}}],
 harvester:[{name:'Isolated converter',values:{duration:30,harvester:'isolated'}},{name:'Capacitive charge sharing',values:{duration:30,harvester:'capacitive'}},{name:'Transfer / collector resistance',values:{duration:30,harvester:'plasma'}},{name:'Mechanical energy',values:{duration:30,harvester:'tribo',sole:'generator'}}],
 emitter:[{name:'Controlled neutralization',values:{duration:120}},{name:'Returning electrons',values:{duration:120,escapeFraction:0}},{name:'Failure after 5 s',values:{duration:120,emitterFailureAt:5}}],
 discharge:[{name:'Challenge reference',values:{duration:30}},{name:'Excess current without a tight limit',values:{duration:30,dischargeResistance:50,currentLimit:10}},{name:'Interrupted contact',values:{duration:30,contactInterruptedAt:.2}}],
}

import test from 'node:test'
import assert from 'node:assert/strict'
import {LunarSimulation,rcTransfer,runExperiment} from '../machines/simulation/lunar-charge-control/engine.js'
import {MODES,SCENARIOS,normalize} from '../machines/simulation/lunar-charge-control/parameters.js'
const near=(a,b,tol=1e-9)=>assert.ok(Math.abs(a-b)<=tol,`${a} != ${b}`)
test('200 pF at -100 kV holds -20 µC and 1 J',()=>{const s=new LunarSimulation('discharge');near(s.q,-20e-6);near(s.fieldEnergy(),1)})
test('RC decay matches analytical solution including current-limited segment',()=>{
 let s=rcTransfer(-100000,100,200e-12,600e6,.0002,1);near(s.voltage,100-100100*Math.exp(-1/.12),1e-8)
 s=rcTransfer(-100000,100,200e-12,10e6,.0002,.01);near(s.voltage,-90000,1e-7)
})
test('Challenge reference reaches electrical target with current below 0.2 mA',()=>{const r=runExperiment('discharge',{duration:30});assert.ok(r.summary.dischargeAt<30);assert.ok(r.summary.peakCurrent<=.0002);near(r.summary.voltage,100,1e-7);near(r.summary.energyResidual,0,1e-8)})
test('isolated converters cannot remove external net charge',()=>{for(const harvester of ['isolated','capacitive','multistage']){const s=new LunarSimulation('harvester',{duration:30,harvester,leakageCurrent:0});const q=s.q;const r=s.advance(30);near(r.charge,q,1e-18);assert.ok(r.harvested>0);near(r.energyResidual,0,1e-8)}})
test('escaping electrons raise a negative potential; returning electrons do not',()=>{
 const no=runExperiment('emitter',{duration:10,escapeFraction:0,additionalCurrent:0,leakageCurrent:0});near(no.summary.voltage,-100000,1e-8)
 const yes=runExperiment('emitter',{duration:10,additionalCurrent:0,leakageCurrent:0});assert.ok(yes.summary.voltage>no.summary.voltage);assert.ok(yes.summary.consumed>0);near(yes.summary.energyResidual,0,1e-8)
})
test('disabled, failed or unpowered emitter cannot remove charge',()=>{for(const values of [{emitterEnabled:false},{emitterFailureAt:0},{initialStorage:0}]){const r=runExperiment('emitter',{duration:1,additionalCurrent:0,...values});near(r.summary.charge,-20e-6,1e-18)}})
test('reference-path harvester transfers charge with separately balanced reference work',()=>{const r=runExperiment('harvester',{duration:5,harvester:'plasma',environmentVoltage:100});assert.ok(r.flows.collector>0);assert.ok(r.summary.harvested>0);near(r.summary.energyResidual,0,1e-8)})
test('internal tribo generation and external charge remain independent',()=>{const a=runExperiment('tribo',{duration:5,sole:'multilayer',leakageCurrent:0}),b=runExperiment('tribo',{duration:5,sole:'generator',leakageCurrent:0});near(a.summary.charge,b.summary.charge,1e-18);assert.ok(b.summary.harvested>a.summary.harvested)})
test('all supplied experiments close charge and energy balances reproducibly',()=>{
 for(const m of MODES)for(const scenario of SCENARIOS[m.id]){const a=runExperiment(m.id,scenario.values),b=runExperiment(m.id,scenario.values);assert.deepEqual(a.summary,b.summary);near(a.summary.energyResidual,0,1e-7);near(a.summary.chargeResidual,0,1e-15);assert.ok(a.samples.every(s=>Object.values(s).every(v=>typeof v!=='number'||Number.isFinite(v))));assert.ok(a.samples.length<=3100)}
})
test('interrupted discharge stays incomplete; high-current case is measurable',()=>{const a=runExperiment('discharge',{duration:30,contactInterruptedAt:.02});assert.equal(a.summary.dischargeAt,null);const b=runExperiment('discharge',{duration:1,dischargeResistance:50,currentLimit:10});assert.ok(b.summary.peakCurrent>.001)})
test('impossible and nonfinite configurations fail explicitly',()=>{for(const input of [{suitCapacitance:0},{efficiency:1.1},{duration:NaN},{stepFrequency:5},{emitterOffVoltage:-3000},{initialStorage:100}])assert.throws(()=>normalize(input))})

test('plasma converges to the analytic current-balance equilibrium',()=>{
 const r=runExperiment('plasma',{duration:300,initialVoltage:0,environmentVoltage:-500,photoCurrent:0});
 near(r.summary.voltage,-500+200*Math.log(.1),.001);assert.ok(Math.abs(r.summary.plasmaCurrent)<1e-13);
});
test('wall-clock scheduling does not change the fixed-step result',()=>{
 for(const mode of MODES){const a=runExperiment(mode.id,{duration:3.21}),b=new LunarSimulation(mode.id,{duration:3.21});for(let i=0;i<25;i++)b.advance(.137);assert.deepEqual(b.result(),a)}
});
test('mechanical work bounds contact charging and an empty energy source stays empty',()=>{
 const a=runExperiment('tribo',{duration:2,stepWork:0,initialVoltage:0,initialStorage:0,sole:'generator'});near(a.summary.charge,0,1e-18);near(a.summary.harvested,0);
 const b=runExperiment('harvester',{duration:2,inputVoltage:0,initialStorage:0});near(b.summary.storage,0);near(b.summary.harvested,0);
});

test('the integrated EVA reference includes a completed current-limited return',()=>{
 const r=runExperiment('system',SCENARIOS.system[0].values);assert.ok(r.summary.dischargeAt!==null&&r.summary.dischargeAt<30);assert.ok(r.summary.peakCurrent<=.0002);near(r.summary.energyResidual,0,1e-7);
});

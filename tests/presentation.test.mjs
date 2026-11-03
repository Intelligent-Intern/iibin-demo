import test from 'node:test'
import assert from 'node:assert/strict'
import {CUES,SHOTS,LEAD_IN,DURATION,presentationAt} from '../frontend/src/lunar/presentation.js'
import {LunarSimulation} from '../machines/simulation/lunar-charge-control/engine.js'
test('editorial timeline preserves every supplied narration timestamp and never starts before fullscreen lead-in',()=>{
 assert.equal(LEAD_IN,5)
 assert.deepEqual(CUES.map(c=>c[0]),[3,7,17,28,37,45,52,60,66,72,83,89,95,106,111,117,123,128,143,149,164,172,180,186,199,206,214,223,228,237,248,253])
 for(let i=0;i<CUES.length;i++){const [at,text]=CUES[i];assert.equal(presentationAt(at).caption,text);if(i)assert.equal(presentationAt(at-.01).caption,CUES[i-1][1])}
 assert.equal(presentationAt(0).caption,'');assert.equal(presentationAt(DURATION).ended,true)
})
test('each camera chapter is reachable and spark rejection appears only at 3:00–3:06',()=>{
 for(let i=0;i<SHOTS.length;i++){const shot=SHOTS[i];assert.ok(shot.until>shot.at);if(i)assert.equal(SHOTS[i-1].until,shot.at);assert.equal(presentationAt(shot.at).shot,shot);assert.ok(shot.offset.every(Number.isFinite))}
 assert.equal(presentationAt(179.99).spark,false);assert.equal(presentationAt(180).spark,true);assert.equal(presentationAt(185.99).spark,true);assert.equal(presentationAt(186).spark,false)
})
test('presentation scenario drives real emitter operation in shadow and a balanced current-limited return',()=>{
 const model=new LunarSimulation('moon',{duration:120,initialVoltage:-100000,shadowVoltage:-10000,dischargeResistance:300})
 const shadow=model.advance(72);assert.equal(shadow.shadow,true);assert.equal(shadow.emitterOn,true)
 const end=model.advance(48);assert.equal(end.finished,true);assert.ok(end.dischargeAt!==null);assert.ok(end.peakCurrent<=.0002);assert.ok(Math.abs(end.energyResidual)<1e-7)
})

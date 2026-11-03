<script setup>
import {ref,onMounted,onBeforeUnmount} from 'vue'
import * as THREE from 'three'
import {OrbitControls} from 'three/addons/controls/OrbitControls.js'
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js'
import {detailSuit,detailLander,detailTerrain,createPlasma} from './scene-detail.js'
import {LEAD_IN,DURATION,presentationAt} from './presentation.js'
import {LunarSimulation} from '../../../machines/simulation/lunar-charge-control/engine.js'
import {SCENARIOS} from '../../../machines/simulation/lunar-charge-control/parameters.js'
import './presentation.css'
const props=defineProps({state:Object,initialComponent:String})
const emit=defineEmits(['bench','presentation-start'])
const stage=ref(null),presenting=ref(false),playing=ref(false),presentationTime=ref(-5),callout=ref(null),subtitle=ref(''),spark=ref(false),fullscreenError=ref('')
const viewport=ref(null),level=ref('environment'),selected=ref('sole'),failed=ref(false)
const components={sole:{name:'Multilayer sole',bench:'tribo'},sensor:{name:'Potential sensors',bench:'plasma'},harvester:{name:'HV energy harvester',bench:'harvester'},storage:{name:'Electrical storage',bench:'harvester'},emitter:{name:'Electron emitter',bench:'emitter'}}
let terrainHeight,plasma,landerGroup,presentationEpoch=0,presentationModel,presentationSamples=[],presentationIndex=0,emission,emissionPositions,emissionMaterial,leadWasHidden=false
let renderer,scene,camera,controls,observer,raf,astronaut,legs=[],field,clock=0,previous=0,transition=0,down
let lastSuitPosition,focusElapsed=0,targets={},textures=[],environment,pmrem
const v=(x,y,z)=>new THREE.Vector3(x,y,z)
let seed=20261101
const random=()=>((seed=Math.imul(seed,1664525)+1013904223>>>0)/4294967296)
function texture(foil=false){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=512;const ctx=canvas.getContext('2d'),data=ctx.createImageData(512,512)
 for(let y=0;y<512;y++)for(let x=0;x<512;x++){const i=(y*512+x)*4,n=random();let a=foil?128+50*Math.sin(x*.23+Math.sin(y*.09)*3)+30*(n-.5):110+(n-.5)*70+14*Math.sin(x*.05)*Math.cos(y*.08);for(let k=0;k<3;k++)data.data[i+k]=a;data.data[i+3]=255}ctx.putImageData(data,0,0)
 const map=new THREE.CanvasTexture(canvas);map.wrapS=map.wrapT=THREE.RepeatWrapping;map.repeat.set(foil?3:10,foil?3:10);textures.push(map);return map
}
function mesh(geometry,material,parent=scene,position=v(0,0,0),component){const m=new THREE.Mesh(geometry,material);m.position.copy(position);m.castShadow=true;m.receiveShadow=true;if(component)m.userData.component=component;parent.add(m);return m}
function strut(a,b,r,material,parent){const d=b.clone().sub(a),m=mesh(new THREE.CylinderGeometry(r,r,d.length(),10),material,parent,a.clone().add(b).multiplyScalar(.5));m.quaternion.setFromUnitVectors(v(0,1,0),d.normalize());return m}
function box(size,material,parent,position,component){return mesh(new RoundedBoxGeometry(...size,3,Math.min(.035,...size.map(n=>n*.18))),material,parent,position,component)}
function suit(){
 const g=new THREE.Group();g.position.set(-1.5,0,2);scene.add(g)
 const cloth=new THREE.MeshStandardMaterial({color:'#d4d8d4',roughness:.88,bumpMap:texture(),bumpScale:.003}),dark=new THREE.MeshStandardMaterial({color:'#202936',roughness:.65}),metal=new THREE.MeshStandardMaterial({color:'#adb7c0',metalness:.85,roughness:.24}),gold=new THREE.MeshPhysicalMaterial({color:'#af7621',metalness:1,roughness:.13,clearcoat:1})
 const main=mesh(new THREE.CapsuleGeometry(.31,.4,8,20),cloth,g,v(0,1.24,0),'suit')
 box([.51,.7,.26],cloth,g,v(0,1.24,-.32),'harvester');box([.33,.18,.06],metal,g,v(0,1.5,-.49),'harvester');box([.28,.22,.08],dark,g,v(0,1.17,-.5),'storage')
 mesh(new THREE.SphereGeometry(.29,28,20),cloth,g,v(0,1.91,0),'suit');const visor=mesh(new THREE.SphereGeometry(.263,28,18,0,Math.PI*2,0,Math.PI*.64),gold,g,v(0,1.94,.055),'suit');visor.rotation.x=Math.PI/2
 const collar=mesh(new THREE.TorusGeometry(.235,.035,10,40),metal,g,v(0,1.68,0),'suit');collar.rotation.x=Math.PI/2
 for(const sign of [-1,1]){
  const leg=new THREE.Group();leg.position.set(sign*.19,.94,0);g.add(leg);legs.push(leg)
  mesh(new THREE.CapsuleGeometry(.13,.47,7,14),cloth,leg,v(0,-.31,0),'suit')
  for(let i=0;i<5;i++){const ring=mesh(new THREE.TorusGeometry(.128,.012,8,28),cloth,leg,v(0,-.48+i*.032,0),'suit');ring.rotation.x=Math.PI/2}
  box([.28,.19,.43],cloth,leg,v(0,-.72,.09),'sole')
  for(let i=0;i<4;i++)box([.285,.022,.44],[dark,metal,dark,metal][i],leg,v(0,-.82-i*.023,.09),'sole')
  for(let j=0;j<5;j++)box([.28,.018,.035],dark,leg,v(0,-.92,-.07+j*.08),'sole')
  const arm=new THREE.Group();arm.position.set(sign*.34,1.5,0);g.add(arm);mesh(new THREE.CapsuleGeometry(.12,.39,7,14),cloth,arm,v(sign*.08,-.27,.04),'suit');arm.rotation.z=sign*.2
  mesh(new THREE.SphereGeometry(.125,16,12),cloth,arm,v(sign*.1,-.56,.08),'suit')
 }
 box([.23,.19,.06],dark,g,v(.07,1.42,.32),'sensor');box([.13,.08,.01],new THREE.MeshStandardMaterial({color:'#2dd4bf',emissive:'#09605b',emissiveIntensity:.4}),g,v(.07,1.44,.355),'sensor')
 const emitter=mesh(new THREE.CylinderGeometry(.055,.07,.29,16),metal,g,v(.3,1.65,-.4),'emitter');emitter.rotation.z=0
 for(let i=0;i<3;i++)mesh(new THREE.TorusGeometry(.065,.009,8,22),dark,g,v(.3,1.57+i*.06,-.4),'emitter').rotation.x=Math.PI/2
 const curve=new THREE.CatmullRomCurve3([v(-.25,1.44,.2),v(-.43,1.12,.3),v(-.3,.97,.04),v(-.32,1.07,-.34)])
 mesh(new THREE.TubeGeometry(curve,24,.035,9,false),dark,g,v(0,0,0),'harvester')
 field=mesh(new THREE.SphereGeometry(1.25,36,24),new THREE.MeshBasicMaterial({color:'#53b5d0',wireframe:true,transparent:true,opacity:.08,depthWrite:false}),g,v(0,1,0));field.scale.set(.65,1,.65);field.castShadow=false
 detailSuit({group:g,mesh,box,strut,texture,legs})
 targets={sole:v(.15,.15,.12),sensor:v(.1,1.4,.3),harvester:v(0,1.4,-.4),storage:v(0,1.1,-.4),emitter:v(.3,1.65,-.4),suit:v(0,1.05,0)}
 return g
}
function lander(){
 const g=new THREE.Group();g.position.set(-7,.1,0);scene.add(g);landerGroup=g
 const foil=new THREE.MeshStandardMaterial({color:'#bc8d3c',metalness:.88,roughness:.38,bumpMap:texture(true),bumpScale:.045}),aluminum=new THREE.MeshStandardMaterial({color:'#a1abb4',metalness:.9,roughness:.3}),black=new THREE.MeshStandardMaterial({color:'#19222e',metalness:.4,roughness:.6})
 mesh(new THREE.CylinderGeometry(1.1,1.5,1.1,8),foil,g,v(0,1.45,0));mesh(new THREE.CylinderGeometry(.78,.85,1.25,8),aluminum,g,v(0,2.6,0));mesh(new THREE.ConeGeometry(.84,.4,8),black,g,v(0,3.42,0))
 box([.52,.43,.04],black,g,v(0,2.83,.8));mesh(new THREE.CylinderGeometry(.2,.48,.65,24,true),black,g,v(0,.58,0))
 for(let i=0;i<4;i++){const a=(i+.5)*Math.PI/2,foot=v(Math.cos(a)*2.4,.1,Math.sin(a)*2.4);strut(v(Math.cos(a)*.9,1.9,Math.sin(a)*.9),foot,.065,aluminum,g);strut(v(Math.cos(a)*1.2,1,Math.sin(a)*1.2),foot,.04,aluminum,g);mesh(new THREE.CylinderGeometry(.38,.4,.08,24),foil,g,foot)}
 for(let i=0;i<8;i++)strut(v(-.24,.3+i*.28,1.2),v(.24,.3+i*.28,1.2),.025,aluminum,g)
 strut(v(-.28,.25,1.22),v(-.28,2.5,1.22),.03,aluminum,g);strut(v(.28,.25,1.22),v(.28,2.5,1.22),.03,aluminum,g)
 strut(v(.4,3.5,0),v(.4,4.4,0),.025,aluminum,g);const dish=mesh(new THREE.SphereGeometry(.4,20,12,0,Math.PI*2,0,.8),aluminum,g,v(.4,4.3,0));dish.rotation.z=.8
 detailLander({group:g,mesh,box,strut,texture})
}
function init(){
 renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(2,devicePixelRatio));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;viewport.value.appendChild(renderer.domElement)
 scene=new THREE.Scene();scene.background=new THREE.Color('#020306');camera=new THREE.PerspectiveCamera(40,1,.03,320);camera.position.set(10,8,15)
 controls=new OrbitControls(camera,renderer.domElement);controls.target.set(-1,1,0);controls.enableDamping=true;controls.minDistance=.3;controls.maxDistance=48;controls.maxPolarAngle=Math.PI*.49
 pmrem=new THREE.PMREMGenerator(renderer)
 // Outdoor reflection capture: lunar ground, black sky and a small solar disc.
 const reflectionScene=new THREE.Scene();reflectionScene.background=new THREE.Color('#000000')
 const reflectionGround=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.MeshBasicMaterial({color:'#74716b'}));reflectionGround.rotation.x=-Math.PI/2;reflectionGround.position.y=-1.8;reflectionScene.add(reflectionGround)
 const solarDisc=new THREE.Mesh(new THREE.SphereGeometry(.32,16,12),new THREE.MeshBasicMaterial({color:new THREE.Color(12,11.5,10.5)}));solarDisc.position.set(-18,4,6);reflectionScene.add(solarDisc)
 environment=pmrem.fromScene(reflectionScene).texture;scene.environment=environment;scene.environmentIntensity=.55
 reflectionGround.geometry.dispose();reflectionGround.material.dispose();solarDisc.geometry.dispose();solarDisc.material.dispose()
 scene.add(new THREE.HemisphereLight('#c0d7ef','#252b36',.18));const sun=new THREE.DirectionalLight('#fff5df',3.4);sun.position.set(-18,4,6);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-22,right:22,top:22,bottom:-22,near:1,far:120});sun.shadow.bias=-.0003;scene.add(sun)
 terrainHeight=detailTerrain({scene,mesh,texture,random})
 const earthCanvas=document.createElement('canvas');earthCanvas.width=512;earthCanvas.height=256;const ec=earthCanvas.getContext('2d');ec.fillStyle='#1b436b';ec.fillRect(0,0,512,256)
 for(let i=0;i<800;i++){const x=random()*512,y=random()*256;ec.fillStyle=i%3?'#9aa5a48c':'#e5ebedaa';ec.beginPath();ec.ellipse(x,y,random()*22+4,random()*4+1,-.3,0,Math.PI*2);ec.fill()}
 const earthMap=new THREE.CanvasTexture(earthCanvas);earthMap.colorSpace=THREE.SRGBColorSpace;textures.push(earthMap)
 mesh(new THREE.SphereGeometry(.9,48,32),new THREE.MeshStandardMaterial({map:earthMap,roughness:.65}),scene,v(-20,11,-38)).castShadow=false
 lander();astronaut=suit();plasma=createPlasma(scene)
 emissionPositions=new Float32Array(160*6);emissionMaterial=new THREE.LineBasicMaterial({color:'#72bfff',transparent:true,opacity:.6,depthWrite:false,blending:THREE.AdditiveBlending})
 emission=new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position',new THREE.BufferAttribute(emissionPositions,3)),emissionMaterial);emission.frustumCulled=false;scene.add(emission)
 observer=new ResizeObserver(()=>{const w=viewport.value.clientWidth,h=viewport.value.clientHeight;if(w&&h){renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}});observer.observe(viewport.value)
 renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointerup',pick)
 raf=requestAnimationFrame(frame)
 if(Object.hasOwn(components,props.initialComponent))focus(props.initialComponent)
}
function pointerDown(e){down={x:e.clientX,y:e.clientY}}
function pick(e){if(presenting.value)return;if(!down||Math.hypot(e.clientX-down.x,e.clientY-down.y)>6)return;const b=renderer.domElement.getBoundingClientRect(),ray=new THREE.Raycaster();ray.setFromCamera({x:(e.clientX-b.left)/b.width*2-1,y:-(e.clientY-b.top)/b.height*2+1},camera);const object=ray.intersectObjects(astronaut.children,true).find(hit=>hit.object.userData.component)?.object;if(object)focus(level.value==='environment'?'suit':object.userData.component==='suit'?'suit':object.userData.component)}
function focus(value){level.value=value;if(value!=='environment'&&value!=='suit')selected.value=value;transition=1;focusElapsed=0;controls.enabled=false}
// A deterministic demonstration run uses the same fixed-step engine as the benches.
// Camera timing is editorial; measured values always come from this run.
function preparePresentation(){
 presentationModel=new LunarSimulation('moon',{...SCENARIOS.moon[0].values,duration:120,initialVoltage:-100000,shadowVoltage:-10000})
 presentationSamples=[presentationModel.snapshot()]
 for(let i=0;i<1200;i++){presentationModel.advance(.1);presentationSamples.push(presentationModel.snapshot())}
 presentationIndex=0
}
async function launchPresentation(){
 fullscreenError.value=''
 try{
  await stage.value.requestFullscreen({navigationUI:'hide'})
  if(document.fullscreenElement!==stage.value)return
  presenting.value=true;playing.value=false;presentationTime.value=-LEAD_IN;callout.value=null;subtitle.value='';controls.enabled=false
  presentationEpoch=performance.now();emit('presentation-start');preparePresentation()
  camera.position.set(21,13,27);controls.target.set(-1,0,-5)
 }catch(e){fullscreenError.value='Fullscreen could not be started. '+e.message}
}
function fullscreenChanged(){if(document.fullscreenElement!==stage.value&&presenting.value){presenting.value=false;playing.value=false;callout.value=null;subtitle.value='';controls.enabled=true;focus('environment')}}
function tourTarget(name){
 if(name==='terrain')return v(-1,0,-5)
 if(name==='crater')return v(6,-.2,-5)
 if(name==='lander')return landerGroup.position.clone().add(v(0,1.8,0))
 if(name==='interface')return landerGroup.position.clone().add(v(1,1.12,1.1))
 return astronaut.position.clone().add(targets[name]||targets.suit)
}
function cinematicPose(t,dt){
 const cue=presentationAt(t),shot=cue.shot,target=tourTarget(shot.target),offset=v(...shot.offset)
 // Slow dolly and orbital parallax within each shot, eased transitions between shots.
 const orbit=(cue.progress-.5)*.14;offset.applyAxisAngle(v(0,1,0),orbit);offset.multiplyScalar(1-cue.progress*.12)
 camera.position.lerp(target.clone().add(offset),1-Math.exp(-dt*1.7));controls.target.lerp(target,1-Math.exp(-dt*2.3));camera.lookAt(controls.target)
 const projected=target.clone().project(camera)
 callout.value={...shot,x:Math.max(8,Math.min(75,(projected.x+1)*50+8)),y:Math.max(18,Math.min(62,(-projected.y+1)*50-12)),anchorX:(projected.x+1)*50,anchorY:(-projected.y+1)*50}
 subtitle.value=cue.caption;spark.value=cue.spark
 if(cue.ended){playing.value=false}
}
function frame(now){
 raf=requestAnimationFrame(frame)
 if(document.hidden){previous=now;leadWasHidden=true;return}
 const elapsed=Math.max(0,(now-previous)/1000||.016),dt=Math.min(.15,elapsed);previous=now;clock+=dt
 if(leadWasHidden){if(presenting.value)presentationEpoch+=elapsed*1000;leadWasHidden=false}
 let s=props.state
 if(presenting.value){
  const t=Math.min(DURATION,(performance.now()-presentationEpoch)/1000-LEAD_IN);presentationTime.value=t;playing.value=t>=0&&t<DURATION
  if(t>=0){
   // The EVA reaches the lander at the corresponding narration chapter.
   const physicalTime=t<95?t/95*45.6:t<164?45.6+(t-95)/69*32.4:t<172?78+(t-164)/8*12:90+Math.min(1,(t-172)/27)*30
   presentationIndex=Math.min(presentationSamples.length-1,Math.floor(physicalTime*10));s=presentationSamples[presentationIndex]
  }else{s=presentationSamples[0]}
 }
 if(s){
  const t=s.time,shadow=s.shadow,x=s.contact?-4.8:shadow?4.7+Math.sin(t*.1):s.phase==='Return'?1:-1+Math.sin(t*.08)*3,z=shadow?-4.2:1.6
  astronaut.position.lerp(v(x,terrainHeight(x,z)+.025,z),Math.min(1,dt*3))
  for(let i=0;i<legs.length;i++)legs[i].rotation.x=s.walking?Math.sin(t*6.28+(i?Math.PI:0))*.16:0
  field.material.color.set(Math.abs(s.voltage)>100000?'#ee775b':'#66c2da');field.material.opacity=presenting.value?(presentationTime.value>=106&&presentationTime.value<123?.04:0):Math.min(.035,.005+Math.abs(s.voltage)/2e6)
  const showPlasma=presenting.value&&presentationTime.value>=83&&presentationTime.value<123
  plasma.update(clock,s,astronaut.position,showPlasma,!presenting.value||showPlasma)
  const emitterOrigin=astronaut.position.clone().add(v(.3,1.82,-.4))
  emission.visible=!!s.emitterOn&&(!presenting.value||presentationTime.value>=149&&presentationTime.value<164)
  for(let i=0;i<160;i++){const phase=(i/160+clock*.6)%1,a=i*2.399,spread=phase*.16,x=emitterOrigin.x+Math.cos(a)*spread,z=emitterOrigin.z+Math.sin(a)*spread,y=emitterOrigin.y+phase*2;emissionPositions.set([x,y,z,x,y+.045,z],i*6)}emission.geometry.attributes.position.needsUpdate=true
 }
 if(presenting.value){if(presentationTime.value>=0)cinematicPose(presentationTime.value,dt);else camera.lookAt(controls.target)}
 else{
  if(level.value!=='environment'&&!transition&&lastSuitPosition){const delta=astronaut.position.clone().sub(lastSuitPosition);camera.position.add(delta);controls.target.add(delta)}
  if(transition){
   const target=level.value==='environment'?v(-1,1,0):astronaut.position.clone().add(targets[level.value]||targets.suit)
   const offset=level.value==='environment'?v(11,7,15):level.value==='suit'?v(2.3,1.2,3.2):['harvester','storage','emitter'].includes(level.value)?v(1,.45,-1.2):v(.7,.35,1)
   focusElapsed+=dt;camera.position.lerp(target.clone().add(offset),Math.min(1,dt*5));controls.target.lerp(target,Math.min(1,dt*5))
   if(focusElapsed>=1.3){transition=0;controls.enabled=true}
  }
  controls.update()
 }
 lastSuitPosition=astronaut.position.clone();renderer.render(scene,camera)
}
onMounted(()=>{document.addEventListener('fullscreenchange',fullscreenChanged);try{init()}catch(e){console.error(e);failed.value=true}})
onBeforeUnmount(()=>{document.removeEventListener('fullscreenchange',fullscreenChanged);plasma?.dispose();if(document.fullscreenElement===stage.value)document.exitFullscreen();cancelAnimationFrame(raf);observer?.disconnect();controls?.dispose();const geometries=new Set(),materials=new Set();scene?.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])materials.add(m)});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());environment?.dispose();pmrem?.dispose();renderer?.dispose();renderer?.forceContextLoss()})
</script>
<template><section ref="stage" class="moon-view" :class="{'is-presentation':presenting}" :data-presentation-time="presenting?Math.max(-5,presentationTime).toFixed(1):undefined"><div ref="viewport" class="moon-canvas" role="img" aria-label="Interactive lunar environment with astronaut suit and lander"/><div v-if="failed" class="scene-fallback">WebGL is unavailable. Measurements, charts and component controls remain available.</div><div v-if="!presenting" class="scene-top"><button class="scene-chip" :class="{active:level==='environment'}" @click="focus('environment')">Lunar environment</button><span>/</span><button class="scene-chip" :class="{active:level==='suit'}" @click="focus('suit')">Space suit</button><span v-if="!['environment','suit'].includes(level)">/ {{components[selected]?.name}}</span></div><div v-if="!presenting&&level!=='environment'" class="component-picker"><button v-for="(component,id) in components" :key="id" :class="{active:level===id}" @click="focus(id)">{{component.name}}</button></div><div v-if="!presenting" class="scene-bottom"><div><span>{{state?.phase||'Lunar environment'}}</span><strong>{{state?.shadow?'Permanent shadow':'Illuminated area'}}</strong><small>Particle flow and field shell are symbolic</small></div><button v-if="!['environment','suit'].includes(level)" class="button" @click="emit('bench',{mode:components[selected].bench,component:selected})">{{components[selected].name}} test bench →</button><button v-else class="scene-chip" @click="focus('suit')">Inspect suit →</button></div><button v-if="!presenting&&!failed" class="presentation-launch" @click="launchPresentation">▶ Play cinematic presentation</button>
 <p v-if="fullscreenError" class="presentation-error" role="alert">{{fullscreenError}}</p>
 <div v-if="presenting" class="cinematic-overlay" :class="{'is-waiting':presentationTime<0,'is-ending':presentationTime>=248}" aria-live="off">
  <div class="cinema-matte cinema-matte--top"/><div class="cinema-matte cinema-matte--bottom"/>
  <template v-if="presentationTime>=0">
   <svg v-if="callout&&presentationTime<248" class="callout-lines" viewBox="0 0 100 100" preserveAspectRatio="none"><path :d="`M ${callout.anchorX} ${callout.anchorY} L ${callout.x-2} ${callout.y+2} L ${callout.x} ${callout.y+2}`"/></svg>
   <Transition name="callout"><aside v-if="callout&&presentationTime<248" :key="callout.at" class="science-callout" :style="{left:callout.x+'%',top:callout.y+'%'}"><span class="callout-index">LCC / {{String(callout.at).padStart(3,'0')}}</span><h2>{{callout.title}}</h2><p>{{callout.detail}}</p><div v-if="presentationTime>=83&&presentationTime<123" class="plasma-legend"><span>Electrons</span><span>Ions</span><span>Photoelectrons</span></div></aside></Transition>
   <div v-if="spark" class="spark-prohibition" aria-label="No uncontrolled spark"><svg viewBox="0 0 100 100"><path class="spark-bolt" d="M 58 10 L 28 53 L 48 53 L 38 90 L 76 40 L 55 40 Z"/><path class="spark-strike" d="M 18 18 L 84 84"/></svg></div>
   <div v-if="presentationTime>=248" class="cinematic-title"><span>LCC / LUNAR EXPLORATION</span><h1>Lunar Charge Control</h1><p v-if="presentationTime>=253">Harness the energy.<br/>Control the charge.<br/>Explore beyond the light.</p></div>
   <Transition name="caption" mode="out-in"><p v-if="subtitle&&presentationTime<248" :key="subtitle" class="cinematic-caption">{{subtitle}}</p></Transition>
  </template>
 </div>
 </section></template>

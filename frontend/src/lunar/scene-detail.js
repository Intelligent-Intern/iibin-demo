import * as T from 'three'
const V=(x,y,z)=>new T.Vector3(x,y,z)
export function detailSuit({group:g,mesh,box,strut,texture,legs}){
 const fabric=new T.MeshStandardMaterial({color:0xe4e2d8,roughness:.82,bumpMap:texture(),bumpScale:.0025})
 const seam=new T.MeshStandardMaterial({color:0x9b9e99,roughness:.9}),rubber=new T.MeshStandardMaterial({color:0x1c252d,roughness:.76})
 const metal=new T.MeshStandardMaterial({color:0xb9c5c8,metalness:.92,roughness:.24}),blue=new T.MeshStandardMaterial({color:0x2a5265,metalness:.55,roughness:.3})
 const red=new T.MeshStandardMaterial({color:0x93332b,roughness:.65})
 const band=(parent,y,r,mat=seam)=>{const m=mesh(new T.TorusGeometry(r,.008,8,40),mat,parent,V(0,y,0),'suit');m.rotation.x=Math.PI/2;return m}
 // Tailored pressure garment: narrow stitch lines, ribs, restraint straps, connectors.
 for(const sign of [-1,1]){
  for(let j=0;j<9;j++)band(g,1.05+j*.046,.301+j*.001)
  const shoulder=mesh(new T.SphereGeometry(.165,24,18),fabric,g,V(sign*.35,1.5,0),'suit');shoulder.scale.set(1,1.05,1.12)
  for(let j=0;j<8;j++){const r=mesh(new T.TorusGeometry(.121,.009,8,28),j===3?red:seam,g,V(sign*.415,1.18-j*.022,.04),'suit');r.rotation.x=Math.PI/2;r.rotation.z=-sign*.2}
  box([.044,.47,.025],seam,g,V(sign*.22,1.34,.283),'suit')
  box([.12,.055,.035],metal,g,V(sign*.22,1.16,.3),'suit')
  for(let j=0;j<3;j++){
   const socket=mesh(new T.CylinderGeometry(.024,.024,.027,20),j===1?blue:metal,g,V(sign*(.12+j*.055),1.18,.318),'sensor');socket.rotation.x=Math.PI/2
  }
  // Distinct fingers, protective knuckles and wrist rings replace spherical mittens.
  for(let j=0;j<4;j++){const finger=mesh(new T.CapsuleGeometry(.018,.075,5,10),fabric,g,V(sign*(.39+j*.029),.86,.13),'suit');finger.rotation.x=.23+j*.08}
  mesh(new T.CapsuleGeometry(.024,.06,5,12),fabric,g,V(sign*.36,.91,.19),'suit').rotation.z=sign*.7
  box([.09,.13,.025],rubber,g,V(sign*.44,.93,.18),'suit')
 }
 for(const leg of legs){
  for(let j=0;j<12;j++)band(leg,-.1-j*.037,.132,j===2?red:seam)
  box([.19,.16,.025],fabric,leg,V(0,-.45,.125),'suit')
  for(const sign of [-1,1])box([.023,.4,.018],seam,leg,V(sign*.11,-.29,.08),'suit')
  for(let j=0;j<7;j++)box([.235,.008,.014],seam,leg,V(0,-.665-j*.015,.285),'sole')
  for(let j=0;j<9;j++)for(const side of [-1,1]){const lug=box([.11,.022,.024],rubber,leg,V(side*.067,-.92,-.08+j*.043),'sole');lug.rotation.y=side*.35}
  for(const x of [-.145,.145])for(let j=0;j<5;j++)box([.004,.009,.055],j%2?blue:metal,leg,V(x,-.83-j*.018,.21),'sole')
 }
 // Helmet rim, locking lugs, sunshade, work lights and communications antenna.
 const rim=mesh(new T.TorusGeometry(.255,.025,12,64),metal,g,V(0,1.93,.14),'suit');rim.scale.set(1,1.04,1)
 for(const sign of [-1,1]){
  box([.075,.075,.1],fabric,g,V(sign*.26,2.02,.06),'suit')
  mesh(new T.CylinderGeometry(.021,.021,.014,24),new T.MeshStandardMaterial({color:0xffedd1,emissive:0xffc985,emissiveIntensity:1.5}),g,V(sign*.26,2.02,.119),'suit').rotation.x=Math.PI/2
  box([.045,.11,.025],rubber,g,V(sign*.255,1.89,.16),'suit')
 }
 box([.3,.055,.09],fabric,g,V(0,2.16,.11),'suit')
 const visor=new T.MeshPhysicalMaterial({color:0xd3a04f,metalness:1,roughness:.075,clearcoat:1,clearcoatRoughness:.06})
 const window=mesh(new T.SphereGeometry(.25,48,32,0,Math.PI*2,0,Math.PI*.48),visor,g,V(0,1.94,.07),'suit');window.rotation.x=Math.PI/2;window.scale.set(1,1,1.04)
 strut(V(-.23,1.6,-.36),V(-.23,2.17,-.36),.009,metal,g)
 // Backpack service panels, fasteners, radiator fins and insulated wiring.
 for(const sign of [-1,1]){
  box([.075,.58,.035],metal,g,V(sign*.215,1.26,-.476),'harvester')
  for(let j=0;j<17;j++)box([.07,.008,.09],metal,g,V(sign*.215,1.02+j*.029,-.51),'harvester')
 }
 box([.285,.18,.025],blue,g,V(0,1.5,-.534),'harvester')
 for(let j=0;j<3;j++)box([.075,.11,.035],metal,g,V(-.085+j*.085,1.14,-.565),'storage')
 for(let y of [1.07,1.23,1.43,1.57])for(let x of [-.135,.135]){
  mesh(new T.CylinderGeometry(.009,.009,.008,8),metal,g,V(x,y,-.555),'harvester').rotation.x=Math.PI/2
 }
 for(let j=0;j<3;j++){
  const curve=new T.CatmullRomCurve3([V(-.17+j*.025,1.47,-.55),V(-.2+j*.025,1.32,-.6),V(-.1+j*.04,1.25,-.58)])
  mesh(new T.TubeGeometry(curve,22,.006,7,false),j===1?red:rubber,g,V(0,0,0),'storage')
 }
 for(let i=0;i<11;i++){const ring=mesh(new T.TorusGeometry(.065,.004,8,32),metal,g,V(.3,1.54+i*.016,-.4),'emitter');ring.rotation.x=Math.PI/2}
 const grid=box([.09,.006,.09],blue,g,V(.3,1.81,-.4),'emitter')
 for(let j=0;j<7;j++)strut(V(.26+j*.013,1.816,-.445),V(.26+j*.013,1.816,-.355),.0015,metal,g)
 // Sensor bezel, tiny readout segments and guarded probe.
 box([.16,.1,.012],metal,g,V(.07,1.44,.366),'sensor')
 box([.135,.075,.008],rubber,g,V(.07,1.44,.376),'sensor')
 const glow=new T.MeshBasicMaterial({color:0x6fe7d5})
 for(let i=0;i<9;i++)box([.008,.013+(i%3)*.008,.003],glow,g,V(.018+i*.013,1.44,.382),'sensor')
 strut(V(.22,1.45,.3),V(.27,1.6,.32),.008,metal,g)
 // Local pressure-garment folds, kept separate from rigid rings and equipment.
 g.traverse(object=>{if(object.geometry?.type!=='CapsuleGeometry')return;const geometry=object.geometry,position=geometry.attributes.position
  for(let i=0;i<position.count;i++){const x=position.getX(i),y=position.getY(i),z=position.getZ(i),r=Math.hypot(x,z);if(r<.015)continue;const angle=Math.atan2(z,x),fold=.004*Math.sin(y*65+angle*5)+.002*Math.sin(y*117-angle*9);position.setXYZ(i,x*(1+fold/r),y,z*(1+fold/r))}geometry.computeVertexNormals()
 })
}
export function detailLander({group:g,mesh,box,strut,texture}){
 const metal=new T.MeshStandardMaterial({color:0x9ba8af,metalness:.92,roughness:.27}),dark=new T.MeshStandardMaterial({color:0x19242b,metalness:.5,roughness:.5})
 const foil=new T.MeshStandardMaterial({color:0xc39a4b,metalness:.91,roughness:.34,bumpMap:texture(true),bumpScale:.018})
 for(let side=0;side<8;side++){
  const a=side*Math.PI/4,normal=V(Math.sin(a),0,Math.cos(a))
  const panel=box([.81,.86,.045],foil,g,normal.clone().multiplyScalar(1.3).add(V(0,1.45,0)));panel.rotation.y=a
  for(const sign of [-1,1]){const rail=box([.027,.89,.025],metal,g,V(sign*.38,0,.03));panel.add(rail);g.remove(rail)}
  for(let i=0;i<5;i++){const seam=box([.77,.012,.012],dark,panel,V(0,-.35+i*.17,.03))}
 }
 for(let i=0;i<4;i++){
  const a=(i+.5)*Math.PI/2,n=V(Math.cos(a),0,Math.sin(a)),foot=n.clone().multiplyScalar(2.4).add(V(0,.1,0))
  const upper=n.clone().multiplyScalar(1.1).add(V(0,1.7,0)),mid=upper.clone().lerp(foot,.55)
  strut(upper,mid,.095,foil,g);strut(mid,foot,.042,metal,g)
  for(let j=0;j<3;j++)strut(n.clone().multiplyScalar(.6+j*.3).add(V(0,1.03,0)),foot,.018,metal,g)
  for(let j=0;j<12;j++){const a2=j*Math.PI/6;strut(foot.clone().add(V(Math.cos(a2)*.07,.04,Math.sin(a2)*.07)),foot.clone().add(V(Math.cos(a2)*.36,.04,Math.sin(a2)*.36)),.008,metal,g)}
 }
 // Segmented engine bell and thermal blanket seams.
 for(let j=0;j<14;j++){const ring=mesh(new T.TorusGeometry(.2+j*.02,.012,8,48),metal,g,V(0,.88-j*.037,0));ring.rotation.x=Math.PI/2}
 box([.62,.68,.08],metal,g,V(0,2.52,.84));box([.51,.55,.09],dark,g,V(0,2.52,.89))
 for(let i=0;i<6;i++)box([.48,.015,.01],metal,g,V(0,2.3+i*.085,.94))
 for(const sign of [-1,1]){
  const glass=new T.MeshPhysicalMaterial({color:0x243f4e,metalness:.8,roughness:.08,clearcoat:1})
  const win=box([.36,.29,.035],glass,g,V(sign*.45,2.98,.64));win.rotation.z=sign*.16
  for(let i=0;i<3;i++)mesh(new T.CylinderGeometry(.055,.08,.24,20),metal,g,V(sign*.84,2.65+i*.18,0)).rotation.z=Math.PI/2
  strut(V(sign*.65,3.2,-.25),V(sign*1.55,3.65,-.25),.017,metal,g)
  const solar=box([1.25,.025,.68],dark,g,V(sign*1.65,3.65,-.25));solar.rotation.z=-sign*.12
  for(let x=0;x<7;x++)for(let z=0;z<4;z++)box([.145,.004,.13],new T.MeshStandardMaterial({color:0x162b49,metalness:.85,roughness:.25}),solar,V(-.52+x*.173,.018,-.25+z*.166))
 }
 // Grounding service connection beside the access ladder.
 box([.24,.32,.16],metal,g,V(1,1.12,1));box([.16,.18,.02],dark,g,V(1,1.12,1.09))
 mesh(new T.TorusGeometry(.058,.013,12,32),metal,g,V(1,1.12,1.11))
 const cable=new T.CatmullRomCurve3([V(1,1.08,1.12),V(1.35,.2,1.5),V(1.9,.08,1.8),V(2.3,.1,1.75)])
 mesh(new T.TubeGeometry(cable,60,.018,10,false),dark,g)
}

export function detailTerrain({scene,mesh,texture,random}){
 const craters=[{x:6,z:-5,r:4,d:.85},{x:19,z:-17,r:8,d:2.6},{x:-19,z:-24,r:6,d:1.8},{x:28,z:12,r:5,d:1.2},{x:-26,z:9,r:7,d:1.9}]
 const height=(x,z)=>{const distance=Math.hypot(x,z);let y=Math.max(0,Math.min(1,(distance-40)/40))*(3+2*Math.sin(x*.11)*Math.cos(z*.09)+1.2*Math.sin(x*.23+z*.17))-.045+.025*Math.sin(x*1.2)*Math.cos(z*1.6)+.012*Math.sin(x*8+z*6);for(const c of craters){const r=Math.hypot(x-c.x,z-c.z);y+=c.d*.65*Math.exp(-(((r-c.r)/(.18*c.r))**2))-c.d*Math.exp(-((r/(.76*c.r))**4))}return y}
 const geom=new T.PlaneGeometry(240,240,512,512);geom.rotateX(-Math.PI/2)
 const pos=geom.attributes.position,colors=[]
 for(let i=0;i<pos.count;i++){const x=pos.getX(i),z=pos.getZ(i),y=height(x,z);pos.setY(i,y);const a=.22+random()*.075+.018*Math.sin(x*.4+z*.6);colors.push(a*1.04,a*1.035,a)}
 geom.setAttribute('color',new T.Float32BufferAttribute(colors,3));geom.computeVertexNormals()
 const ground=mesh(geom,new T.MeshStandardMaterial({vertexColors:true,roughness:.98,bumpMap:texture(),bumpScale:.028}),scene)
 const rockShape=new T.IcosahedronGeometry(1,2),rockVertices=rockShape.attributes.position;for(let i=0;i<rockVertices.count;i++){const x=rockVertices.getX(i),y=rockVertices.getY(i),z=rockVertices.getZ(i),factor=1+.14*Math.sin(x*13+y*7+z*19)+.08*Math.sin(x*29-z*11);rockVertices.setXYZ(i,x*factor,y*factor,z*factor)}
 const rocks=new T.InstancedMesh(rockShape,new T.MeshStandardMaterial({color:0x696864,roughness:.95,bumpMap:texture(),bumpScale:.015}),2200),dummy=new T.Object3D()
 for(let i=0;i<2200;i++){const x=(random()-.5)*130,z=(random()-.5)*130,r=(Math.abs(z-1.6)<.65&&Math.abs(x)<6||Math.hypot(x-4.7,z+4.2)<1.4)?.012:.015+random()**5*.8;dummy.position.set(x,height(x,z)+r*.22,z);dummy.rotation.set(random()*6,random()*6,random()*6);dummy.scale.set(r,r*(.4+random()*.5),r*(.6+random()*.6));dummy.updateMatrix();rocks.setMatrixAt(i,dummy.matrix)}
 rocks.castShadow=true;rocks.receiveShadow=true;scene.add(rocks)
 // Sparse stars. No atmosphere, fog or blue sky dome.
 const stars=[];for(let i=0;i<900;i++){const a=random()*Math.PI*2,b=.03+random()*1.4;stars.push(Math.cos(a)*120*Math.cos(b),120*Math.sin(b),Math.sin(a)*120*Math.cos(b))}
 scene.add(new T.Points(new T.BufferGeometry().setAttribute('position',new T.Float32BufferAttribute(stars,3)),new T.PointsMaterial({color:0xcbd1d7,size:.065,sizeAttenuation:true,transparent:true,opacity:.6})))
 // Paired tread impressions along the EVA route.
 const tread=new T.InstancedMesh(new T.BoxGeometry(.045,.003,.18),new T.MeshStandardMaterial({color:0x292a28,roughness:1}),420)
 for(let i=0;i<420;i++){const step=Math.floor(i/7),x=-4.4+(step/60)*8,z=1.6+(step%2?.16:-.16);dummy.position.set(x+(i%7)*.018,height(x,z)+.003,z);dummy.rotation.set(0,Math.PI/2,0);dummy.scale.set(1,1,1);dummy.updateMatrix();tread.setMatrixAt(i,dummy.matrix)}scene.add(tread)
 return height
}

export function createPlasma(scene){
 const count=720,positions=new Float32Array(count*6),colors=new Float32Array(count*6),seeds=Array.from({length:count},(_,i)=>({phase:(i*.61803398875)%1,angle:i*2.39996323,radius:.65+(i%31)/31*3,species:i%3}))
 const palette=[new T.Color('#63b6ff'),new T.Color('#f6ae62'),new T.Color('#c79fff')]
 for(let i=0;i<count;i++)for(let k=0;k<2;k++)palette[seeds[i].species].toArray(colors,i*6+k*3)
 const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));geometry.setAttribute('color',new T.BufferAttribute(colors,3))
 const material=new T.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.35,depthWrite:false,blending:T.AdditiveBlending}),lines=new T.LineSegments(geometry,material);lines.frustumCulled=false;scene.add(lines)
 const glowCanvas=document.createElement('canvas');glowCanvas.width=glowCanvas.height=64;const ctx=glowCanvas.getContext('2d'),gradient=ctx.createRadialGradient(32,32,0,32,32,32);gradient.addColorStop(0,'#ffffff');gradient.addColorStop(.2,'#ffffff88');gradient.addColorStop(1,'#ffffff00');ctx.fillStyle=gradient;ctx.fillRect(0,0,64,64)
 const glow=new T.CanvasTexture(glowCanvas),dots=new T.Points(geometry,new T.PointsMaterial({size:.04,map:glow,vertexColors:true,transparent:true,opacity:.7,depthWrite:false,blending:T.AdditiveBlending}));dots.frustumCulled=false;scene.add(dots)
 function update(time,state,origin,emphasis=false,visible=true){
  lines.visible=visible;dots.visible=visible;if(!visible)return
  material.opacity=emphasis?.46:.11;dots.material.opacity=emphasis?.8:.24
  for(let i=0;i<count;i++){
   const seed=seeds[i],speed=seed.species===0?.36:seed.species===1?.12:.24,f=(seed.phase+time*speed)%1,angle=seed.angle+f*.4,photo=seed.species===2
   const active=!photo||!state?.shadow,rad=photo?.38+f*3.2:seed.radius*(1-f*.84),height=photo?1.7+f*1.4:3.5-f*2.8
   const x=origin.x+Math.cos(angle)*rad,y=origin.y+height,z=origin.z+Math.sin(angle)*rad
   positions.set([x,y,z,x+Math.cos(angle)*.045,y+(photo?-.09:.12),z+Math.sin(angle)*.045],i*6)
   if(!active)positions.fill(0,i*6,i*6+6)
  }geometry.attributes.position.needsUpdate=true
 }
 return {update,dispose:()=>glow.dispose()}
}

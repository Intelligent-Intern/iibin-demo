<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

const emit = defineEmits(['state', 'complete'])
const viewport = ref(null)
const stage = ref('ready')
const elapsed = ref(0)
const pressure = ref(0)
const leak = ref(false)
const guardOpen = ref(false)
const cutaway = ref(false)
const sound = ref(false)
const renderError = ref(false)
const readings = ref([])
const paused = ref(false)
let renderer, scene, camera, controls, observer, animation, guard, clamp, piston, flow, particles, lightRing
let guardAngle = 0, clampY = 0, lastSample = -1, lastTime = 0, audioContext
const disposableTextures = []
const running = computed(() => ['filling', 'settling', 'measuring'].includes(stage.value))
const phaseName = computed(() => ({ ready: 'Prüfbereit', filling: 'Druck aufbauen', settling: 'Druck stabilisieren', measuring: 'Dichtheit messen', passed: 'Ventil dicht', failed: 'Leck erkannt' }[stage.value]))
const progress = computed(() => Math.min(100, elapsed.value * 10))
const chartPath = computed(() => readings.value.map((p, i) => `${i ? 'L' : 'M'}${(p.t / 10 * 540 + 42).toFixed(1)},${(147 - p.p / 6.5 * 120).toFixed(1)}`).join(' '))
const currentState = () => ({ machine: 'valve-leak-test', stage: stage.value, elapsed: Number(elapsed.value.toFixed(2)), pressure: Number(pressure.value.toFixed(3)), leak: leak.value, guardOpen: guardOpen.value, paused: paused.value, result: stage.value === 'passed' ? 'pass' : stage.value === 'failed' ? 'fail' : null })
function publish() { emit('state', currentState()) }
function startTest() {
  if (running.value) return false
  if (guardOpen.value) return false
  readings.value = [{ t: 0, p: 0 }]; elapsed.value = 0; pressure.value = 0
  lastSample = -1; stage.value = 'filling'; paused.value = false; publish(); return true
}
function pauseTest() { if (!running.value) return false; paused.value = !paused.value; publish(); return true }
function resetTest() { stage.value = 'ready'; elapsed.value = 0; pressure.value = 0; readings.value = []; paused.value = false; publish() }
function setLeak(value) { if (running.value) return false; leak.value = Boolean(value); resetTest(); return true }
function toggleGuard() { if (running.value) return false; guardOpen.value = !guardOpen.value; publish(); return true }
function resetView() { if (!camera) return; camera.position.set(6.3, 4.6, 7.3); controls.target.set(0, 1.5, 0); controls.update() }
function toggleCutaway() { cutaway.value = !cutaway.value; scene?.getObjectByName('valve-shell')?.traverse(n => { if (n.isMesh) n.visible = !cutaway.value }); publish() }
function tone(frequency) {
  if (!sound.value) return
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)()
    const oscillator = audioContext.createOscillator(), gain = audioContext.createGain()
    oscillator.frequency.value = frequency; gain.gain.setValueAtTime(.04, audioContext.currentTime)
    gain.gain.exponentialRampToValueAtTime(.001, audioContext.currentTime + .2)
    oscillator.connect(gain); gain.connect(audioContext.destination); oscillator.start(); oscillator.stop(audioContext.currentTime + .2)
  } catch { /* Audio is optional; machine state remains unaffected. */ }
}
function bevelBox(w, h, d, radius = .035) {
  const shape = new THREE.Shape(), x = -w / 2, y = -h / 2, r = Math.min(radius, w / 4, h / 4)
  shape.moveTo(x + r, y); shape.lineTo(x + w - r, y); shape.quadraticCurveTo(x + w, y, x + w, y + r)
  shape.lineTo(x + w, y + h - r); shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  shape.lineTo(x + r, y + h); shape.quadraticCurveTo(x, y + h, x, y + h - r)
  shape.lineTo(x, y + r); shape.quadraticCurveTo(x, y, x + r, y)
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: Math.max(.001, d - r * .4), bevelEnabled: true, bevelSegments: 3, steps: 1, bevelSize: r * .2, bevelThickness: r * .2, curveSegments: 8 })
  geometry.translate(0, 0, -d / 2 + r * .2); return geometry
}
function labelTexture(text, subtext, background = '#e8eef2', ink = '#153146') {
  const canvas = document.createElement('canvas'); canvas.width = 768; canvas.height = 256
  const ctx = canvas.getContext('2d'); ctx.fillStyle = background; ctx.fillRect(0, 0, 768, 256)
  ctx.fillStyle = ink; ctx.font = '700 74px Arial, sans-serif'; ctx.fillText(text, 32, 108)
  ctx.font = '34px Arial, sans-serif'; ctx.fillText(subtext, 35, 182)
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; disposableTextures.push(texture); return texture
}
function initScene() {
  scene = new THREE.Scene(); scene.background = new THREE.Color('#e8eef3'); scene.fog = new THREE.Fog('#e8eef3', 15, 34)
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.25; renderer.outputColorSpace = THREE.SRGBColorSpace
  viewport.value.appendChild(renderer.domElement)
  const room = new RoomEnvironment(), generator = new THREE.PMREMGenerator(renderer)
  const environment = generator.fromScene(room, .04); scene.environment = environment.texture
  disposableTextures.push(environment); room.dispose(); generator.dispose()
  camera = new THREE.PerspectiveCamera(35, 1, .1, 80)
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = .075
  controls.minDistance = 4; controls.maxDistance = 15; controls.maxPolarAngle = Math.PI * .48; controls.minPolarAngle = .2
  controls.enablePan = false; resetView()
  const material = (color, metalness = 0, roughness = .4, extras = {}) => new THREE.MeshStandardMaterial({ color, metalness, roughness, ...extras })
  const alloy = material('#bdcbd5', .92, .27), edge = material('#73889a', .86, .32), dark = material('#173343', .55, .36)
  const blue = material('#124ddb', .48, .25), brass = material('#b79b52', .85, .25), rubber = material('#152328', .05, .57)
  const white = material('#e0e9ef', .25, .35), red = material('#d52e26', .18, .32)
  const glass = new THREE.MeshPhysicalMaterial({ color: '#c2e3ed', metalness: 0, roughness: .08, transmission: .86, thickness: .05, transparent: true, opacity: .23, depthWrite: false, side: THREE.DoubleSide, ior: 1.46 })
  const mesh = (geometry, mat, position = [0, 0, 0], parent = scene) => { const object = new THREE.Mesh(geometry, mat); object.position.set(...position); object.castShadow = mat !== glass; object.receiveShadow = true; parent.add(object); return object }
  const box = (w, h, d, mat, position, parent) => mesh(bevelBox(w, h, d), mat, position, parent)
  const cylinder = (r, h, mat, position, axis = 'y', parent = scene, segments = 48) => {
    const object = mesh(new THREE.CylinderGeometry(r, r, h, segments), mat, position, parent)
    if (axis === 'x') object.rotation.z = Math.PI / 2
    if (axis === 'z') object.rotation.x = Math.PI / 2
    return object
  }
  const bolt = (x, y, z, parent = scene, size = .046) => {
    cylinder(size * 1.4, .014, dark, [x, y, z], 'y', parent)
    cylinder(size, .035, alloy, [x, y + .019, z], 'y', parent, 6)
    box(size * 1.1, .008, .012, dark, [x, y + .039, z], parent)
  }
  const pipe = (points, radius, mat, parent = scene) => mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p))), 64, radius, 12, false), mat, [0, 0, 0], parent)
  // Powder-coated cabinet and machined stainless bed.
  box(4.7, .18, 3.35, alloy, [0, .98, 0]); box(4.52, .72, 3.16, dark, [0, .53, 0])
  box(4.58, .045, 3.22, edge, [0, .855, 0]); box(4.56, .045, 3.22, blue, [0, .15, 0])
  for (const x of [-1.95, 1.95]) for (const z of [-1.25, 1.25]) { cylinder(.135, .16, rubber, [x, .04, z]); cylinder(.08, .16, alloy, [x, .16, z]) }
  for (const x of [-1.95, 1.95]) for (const z of [-1.22, 1.22]) bolt(x, 1.085, z)
  // Front service panel, vents, manufacturer plate and physical emergency-stop.
  box(2.6, .45, .04, blue, [-.65, .55, 1.595])
  const plaque = new THREE.MeshBasicMaterial({ map: labelTexture('VP—01', 'VALVE LEAK TEST / 06 BAR', '#124ddb', '#ffffff') })
  mesh(new THREE.PlaneGeometry(1.55, .52), plaque, [-.7, .56, 1.622])
  for (let i = 0; i < 7; i++) box(.4, .022, .018, rubber, [1.3, .4 + i * .045, 1.601])
  cylinder(.19, .025, material('#f0c847', .2, .4), [1.93, .66, 1.62], 'z')
  cylinder(.115, .12, red, [1.93, .66, 1.69], 'z')
  // T-slot fixture plate and locating pins.
  box(3.55, .13, 2.35, alloy, [0, 1.145, 0])
  for (const z of [-.76, -.38, 0, .38, .76]) box(3.32, .01, .032, dark, [0, 1.217, z])
  for (const x of [-1.47, 1.47]) for (const z of [-.92, .92]) bolt(x, 1.22, z, scene, .055)
  // Rear slotted aluminium-extrusion portal with fasteners.
  for (const x of [-1.95, 1.95]) {
    box(.16, 2.7, .16, alloy, [x, 2.32, -.97])
    box(.035, 2.5, .015, dark, [x, 2.3, -.88]); box(.23, .13, .3, edge, [x, 1.18, -.97])
    bolt(x, 1.25, -.86)
  }
  box(4.06, .16, .16, alloy, [0, 3.61, -.97]); box(3.86, .028, .018, dark, [0, 3.61, -.88])
  box(3.74, 1.35, .06, white, [0, 2.75, -1.03])
  // Pneumatic pressure regulator and dial, credible connection layout.
  cylinder(.27, .19, dark, [-1.18, 2.85, -.78], 'z')
  cylinder(.238, .03, alloy, [-1.18, 2.85, -.67], 'z')
  const dial = document.createElement('canvas'); dial.width = 256; dial.height = 256
  const dc = dial.getContext('2d'); dc.fillStyle = '#f4f7fa'; dc.fillRect(0, 0, 256, 256); dc.strokeStyle = '#173343'; dc.lineWidth = 3
  for (let i = 0; i <= 30; i++) { const a = Math.PI * (.75 + i / 30 * 1.5); dc.beginPath(); dc.moveTo(128 + Math.cos(a) * 95, 128 + Math.sin(a) * 95); dc.lineTo(128 + Math.cos(a) * (i % 5 ? 85 : 75), 128 + Math.sin(a) * (i % 5 ? 85 : 75)); dc.stroke() }
  dc.font = 'bold 32px Arial'; dc.textAlign = 'center'; dc.fillText('0–6', 128, 170); dc.font = '20px Arial'; dc.fillText('bar', 128, 196)
  const dialMap = new THREE.CanvasTexture(dial); dialMap.colorSpace = THREE.SRGBColorSpace; disposableTextures.push(dialMap)
  mesh(new THREE.CircleGeometry(.218, 64), new THREE.MeshBasicMaterial({ map: dialMap }), [-1.18, 2.85, -.647])
  piston = new THREE.Group(); piston.position.set(-1.18, 2.85, -.639); scene.add(piston)
  const needle = box(.012, .175, .007, red, [0, .058, 0], piston); needle.rotation.z = -.08
  cylinder(.018, .014, dark, [0, 0, .012], 'z', piston)
  box(.41, .42, .26, dark, [-1.18, 2.38, -.77]); cylinder(.16, .16, rubber, [-1.18, 2.66, -.77]);
  const instruction = new THREE.MeshBasicMaterial({ map: labelTexture('DICHTHEIT', 'PRÜFDRUCK 6,0 BAR · 10 S', '#e0e9ef') })
  mesh(new THREE.PlaneGeometry(1.35, .45), instruction, [.63, 3.03, -.985])
  // Valve body: turned cylindrical housing, hex union nuts and visible seals.
  const shell = new THREE.Group(); shell.name = 'valve-shell'; shell.position.set(0, 1.76, .07); scene.add(shell)
  const lathePoints = [[.0,-.52],[.22,-.52],[.25,-.48],[.25,-.28],[.32,-.24],[.34,-.18],[.34,.18],[.32,.24],[.25,.28],[.25,.48],[.22,.52],[.0,.52]].map(([r,y]) => new THREE.Vector2(r,y))
  const body = mesh(new THREE.LatheGeometry(lathePoints, 80), alloy, [0, 0, 0], shell); body.rotation.z = Math.PI / 2
  for (const x of [-.37, .37]) { const ring = mesh(new THREE.TorusGeometry(.253, .018, 12, 64), dark, [x, 0, 0], shell); ring.rotation.y = Math.PI / 2 }
  for (const x of [-.63, .63]) {
    cylinder(.245, .22, brass, [x, 1.76, .07], 'x', scene, 6)
    cylinder(.166, .17, alloy, [x + Math.sign(x) * .16, 1.76, .07], 'x')
    for (let i = 0; i < 4; i++) cylinder(.17, .013, edge, [x + Math.sign(x) * (.1 + .027 * i), 1.76, .07], 'x')
    cylinder(.19, .035, rubber, [x + Math.sign(x) * .26, 1.76, .07], 'x')
  }
  // Internal seat, poppet and return spring become visible in section mode.
  cylinder(.12, .91, brass, [0, 1.76, .07], 'x')
  cylinder(.205, .075, rubber, [.11, 1.76, .07], 'x')
  const springPoints = []; for (let i = 0; i <= 240; i++) { const t = i / 240; springPoints.push([-.3 + t * .43, 1.76 + Math.cos(t * Math.PI * 18) * .15, .07 + Math.sin(t * Math.PI * 18) * .15]) }
  pipe(springPoints, .012, alloy)
  cylinder(.18, .21, brass, [0, 2.05, .07]); box(.46, .38, .43, blue, [0, 2.3, .07]); cylinder(.08, .1, dark, [0, 2.54, .07])
  const actuatorPlate = new THREE.MeshBasicMaterial({ map: labelTexture('V-014', 'NC / DN 15', '#124ddb', '#ffffff') })
  mesh(new THREE.PlaneGeometry(.37, .14), actuatorPlate, [0, 2.32, .291])
  for (const x of [-.155, .155]) for (const z of [-.08, .22]) bolt(x, 2.5, z, scene, .024)
  // Locating cradle and guided pneumatic clamping gantry.
  for (const x of [-.4, .4]) { box(.23, .25, .66, edge, [x, 1.35, .07]); box(.25, .055, .56, rubber, [x, 1.49, .07]) }
  for (const x of [-1.08, 1.08]) { box(.38, .11, .75, edge, [x, 1.3, .07]); cylinder(.065, 1.45, alloy, [x, 2.05, -.26]); bolt(x, 1.365, .3) }
  box(2.45, .15, .52, dark, [0, 2.8, -.26]); cylinder(.19, .6, blue, [0, 3.1, -.26]); cylinder(.2, .06, alloy, [0, 3.42, -.26]);
  clamp = new THREE.Group(); scene.add(clamp)
  cylinder(.07, .39, alloy, [0, 2.6, -.26], 'y', clamp); box(.69, .13, .65, edge, [0, 2.46, -.26], clamp)
  for (const x of [-.285, .285]) { box(.1, .35, .12, dark, [x, 2.24, -.1], clamp); box(.12, .1, .16, rubber, [x, 2.04, -.1], clamp) }
  // Flexible polyurethane pneumatic lines with strain relief sleeves.
  pipe([[-.94,1.76,.07],[-1.35,1.76,.07],[-1.5,1.93,-.17],[-1.52,2.24,-.45],[-1.18,2.23,-.68]], .055, blue)
  pipe([[.94,1.76,.07],[1.45,1.76,.12],[1.63,1.96,-.3],[1.5,2.55,-.75],[.45,2.6,-.83]], .052, rubber)
  for (const x of [-.97, .97]) cylinder(.075, .18, brass, [x, 1.76, .07], 'x')
  flow = pipe([[-1.48,1.9,-.13],[-1.34,1.76,.07],[-.9,1.76,.07],[-.35,1.76,.07],[.3,1.76,.07],[.94,1.76,.07],[1.4,1.78,.1]], .025, new THREE.MeshBasicMaterial({ color: '#36d6ff', transparent: true, opacity: 0, depthTest: false }))
  flow.renderOrder = 10
  // Guard: hinged polycarbonate door, brushed frame, discrete handle.
  guard = new THREE.Group(); guard.position.set(-1.88, 1.13, 1.08); scene.add(guard)
  box(3.76, 2.24, .035, glass, [1.88, 1.12, 0], guard)
  for (const x of [0, 3.76]) box(.065, 2.31, .07, alloy, [x, 1.12, 0], guard)
  for (const y of [0, 2.24]) box(3.82, .065, .07, alloy, [1.88, y, 0], guard)
  for (const y of [.3, 1.85]) { cylinder(.075, .23, edge, [0, y, 0], 'y', guard); box(.16, .12, .07, edge, [.08, y, .05], guard) }
  pipe([[3.44,.85,.05],[3.44,.85,.22],[3.44,1.3,.22],[3.44,1.3,.05]], .045, dark, guard)
  for (const x of [-1.88,1.88]) { box(.035, 2.24, 2, glass, [x, 2.25, .08]); for (const z of [-.94, 1.08]) box(.05, 2.3, .05, alloy, [x,2.25,z]) }
  // Thin task light under crossbeam and status strip, no decorative status dots.
  lightRing = new THREE.MeshStandardMaterial({ color: '#25b6c7', emissive: '#16a6be', emissiveIntensity: .6 })
  box(3.68, .018, .045, lightRing, [0, 3.5, -.83])
  const taskLight = new THREE.PointLight('#ddf5ff', 10, 4, 2); taskLight.position.set(0, 3.3, .3); scene.add(taskLight)
  const key = new THREE.DirectionalLight('#ffffff', 4.2); key.position.set(3, 8, 5); key.castShadow = true; key.shadow.mapSize.set(2048,2048)
  key.shadow.camera.left=-6; key.shadow.camera.right=6; key.shadow.camera.top=6; key.shadow.camera.bottom=-6; key.shadow.normalBias=.035; key.shadow.bias=-.0001; scene.add(key)
  const fill = new THREE.DirectionalLight('#b5dcff', 1.5); fill.position.set(-4, 4, -3); scene.add(fill)
  scene.add(new THREE.HemisphereLight('#f6fbff','#8d9ba6',1.6))
  const ground = mesh(new THREE.PlaneGeometry(200,200), material('#e8eef3',0,.82), [0,-.055,0]); ground.rotation.x=-Math.PI/2; ground.castShadow=false
  // Leak particles indicate the actual simulated joint during pressure hold.
  const particleGeometry = new THREE.BufferGeometry(); const positions = new Float32Array(40 * 3); particleGeometry.setAttribute('position',new THREE.BufferAttribute(positions,3))
  particles = new THREE.Points(particleGeometry,new THREE.PointsMaterial({ color: '#eb6049', size: .038, transparent:true, opacity:.85, depthWrite:false })); particles.visible=false; scene.add(particles)
  observer = new ResizeObserver(resize); observer.observe(viewport.value); resize(); lastTime = performance.now(); animate(lastTime)
}
function resize() { if (!renderer || !viewport.value) return; const { width, height } = viewport.value.getBoundingClientRect(); if (!width || !height) return; renderer.setSize(width,height); camera.aspect=width/height; camera.updateProjectionMatrix() }
function animate(now) {
  animation = requestAnimationFrame(animate); const dt = Math.min((now-lastTime)/1000,.1); lastTime=now
  if (running.value && !paused.value) {
    elapsed.value=Math.min(10,elapsed.value+dt); const t=elapsed.value
    stage.value=t<3?'filling':t<5?'settling':'measuring'
    pressure.value=t<3?6*(1-Math.pow(1-t/3,2)):t<5?6-.012*(t-3):5.976-(t-5)*(leak.value ? .19 : .003)
    const sample=Math.floor(t*10); if(sample!==lastSample) { lastSample=sample;readings.value.push({t,p:pressure.value});publish() }
    if(t>=10) { stage.value=leak.value?'failed':'passed';tone(leak.value?280:740);publish();emit('complete',currentState()) }
  }
  guardAngle += ((guardOpen.value ? -Math.PI*.58 : 0)-guardAngle)*Math.min(1,dt*6); if(guard) guard.rotation.y=guardAngle
  clampY += ((guardOpen.value ? .23 : 0)-clampY)*Math.min(1,dt*6); if(clamp) clamp.position.y=clampY
  if(piston) piston.rotation.z=Math.PI*.75-pressure.value/6*Math.PI*1.5
  if(flow) flow.material.opacity=running.value ? .4+Math.sin(now*.007)*.16 : 0
  if(lightRing) { const color=stage.value==='failed'?'#ef613c':stage.value==='passed'?'#00a485':'#25b6c7';lightRing.color.set(color);lightRing.emissive.set(color) }
  if(particles) {
    particles.visible=leak.value&&elapsed.value>5&&(running.value||stage.value==='failed')
    if(particles.visible) { const pos=particles.geometry.attributes.position; for(let i=0;i<40;i++){ const a=(now*.00035+i/40)%1;pos.setXYZ(i,.48+a*.9,1.82+a*.7+Math.sin(i*1.7)*a*.18,.2+Math.cos(i*2.1)*a*.3) }pos.needsUpdate=true }
  }
  controls?.update();renderer?.render(scene,camera)
}
onMounted(() => { try { initScene(); publish() } catch(error) { renderError.value=true; console.error('Valve test 3D initialization failed:',error) } })
onBeforeUnmount(() => {
  cancelAnimationFrame(animation);observer?.disconnect();controls?.dispose();audioContext?.close()
  const geometries=new Set(),materials=new Set();scene?.traverse(n=>{if(n.geometry)geometries.add(n.geometry);if(n.material)(Array.isArray(n.material)?n.material:[n.material]).forEach(m=>materials.add(m))})
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());disposableTextures.forEach(t=>t.dispose());renderer?.dispose();renderer?.domElement.remove()
})
defineExpose({startTest,pauseTest,resetTest,setLeak,toggleGuard,currentState})
</script>

<template>
  <section class="valve-lab" aria-label="Ventil-Dichtheitsprüfung">
    <div class="lab-workspace">
      <div class="scene-panel">
        <div class="scene-title"><div><span class="eyebrow">Prüftechnik / VP-01</span><h2>Ventil-Dichtheitsprüfung</h2></div><span class="simulation-label">Simulation</span></div>
        <div ref="viewport" class="scene-viewport" aria-label="Interaktiver 3D-Prüfstand. Mit der Maus drehen und mit dem Mausrad zoomen."></div>
        <div v-if="renderError" class="scene-fallback">Die 3D-Ansicht benötigt WebGL. Bitte Hardwarebeschleunigung im Browser aktivieren.</div>
        <div class="scene-tools"><button type="button" @click="resetView" title="Kamera zurücksetzen"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8V4m0 4h4M5 8a8 8 0 1 1-1 7"/></svg>Ansicht</button><button type="button" :class="{selected:cutaway}" :aria-pressed="cutaway" @click="toggleCutaway"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 7 8-4 8 4v10l-8 4-8-4ZM4 7l8 4 8-4M12 11v10M4 17l16-10"/></svg>Schnittansicht</button><span>Drehen · Ziehen / Zoom · Mausrad</span></div>
        <div class="scene-caption"><span>V-014 / Kühlmittelventil</span><span>DN 15 · Aluminium · pneumatisch</span></div>
      </div>
      <aside class="control-panel">
        <div class="control-heading"><span class="eyebrow">Prüfauftrag</span><strong>VP-2026-0148</strong><span>Kühlmittelventil · Los 024</span></div>
        <div class="state-banner" :class="{passed:stage==='passed',failed:stage==='failed'}"><span>{{ paused ? 'Prüfung pausiert' : phaseName }}</span><strong>{{ pressure.toFixed(2).replace('.',',') }} <small>bar</small></strong></div>
        <div class="test-facts"><div><span>Prüfdruck</span><strong>6,00 bar</strong></div><div><span>Messdauer</span><strong>5 s</strong></div><div><span>Grenzwert Druckverlust</span><strong>0,10 bar</strong></div><div><span>Schutzhaube</span><strong>{{guardOpen?'Geöffnet':'Geschlossen'}}</strong></div></div>
        <fieldset class="specimen-selector" :disabled="running"><legend>Prüfling wählen</legend><div><button type="button" :class="{active:!leak}" :aria-pressed="!leak" @click="setLeak(false)">Dichtes Ventil</button><button type="button" :class="{active:leak}" :aria-pressed="leak" @click="setLeak(true)">Mit Leckage</button></div></fieldset>
        <div class="main-controls"><button type="button" class="primary" :disabled="guardOpen" @click="running?pauseTest():startTest()"><svg viewBox="0 0 24 24" aria-hidden="true"><path v-if="running&&!paused" d="M8 5v14M16 5v14"/><path v-else d="m8 4 12 8-12 8Z"/></svg>{{running?(paused?'Fortsetzen':'Pausieren'):'Prüfung starten'}}</button><button type="button" class="reset" @click="resetTest" aria-label="Prüfung zurücksetzen" title="Prüfung zurücksetzen"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8V4m0 4h4M5 8a8 8 0 1 1-1 7"/></svg></button></div>
        <button type="button" class="guard-button" :disabled="running" @click="toggleGuard">{{guardOpen?'Schutzhaube schließen':'Schutzhaube öffnen'}}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 20h14V4H5ZM14 12h2"/></svg></button>
        <p v-if="guardOpen" class="guard-hint">Schutzhaube schließen, um die Prüfung zu starten.</p>
        <div v-if="stage==='passed'||stage==='failed'" class="test-result" aria-live="polite"><strong>{{stage==='passed'?'Prüfung bestanden':'Prüfung nicht bestanden'}}</strong><span>{{stage==='passed'?'Druckverlust innerhalb der Toleranz.':'Druckverlust an der rechten Ventilverbindung.'}}</span><span>Δp {{(5.976-pressure).toFixed(3).replace('.',',')}} bar / 5 s</span></div>
      </aside>
    </div>
    <div class="measurement-panel">
      <div class="measurement-header"><div><span class="eyebrow">Live-Messung</span><h3>Druckverlauf</h3></div><div class="measurement-time"><strong>{{elapsed.toFixed(1).replace('.',',')}}<span> / 10,0 s</span></strong><button type="button" :aria-pressed="sound" @click="sound=!sound">{{sound?'Prüfton an':'Prüfton aus'}}</button></div></div>
      <div class="phase-track"><div :class="{current:stage==='filling',done:elapsed>=3}"><span>01</span>Druckaufbau<small>0–3 s</small></div><div :class="{current:stage==='settling',done:elapsed>=5}"><span>02</span>Stabilisierung<small>3–5 s</small></div><div :class="{current:stage==='measuring',done:elapsed>=10}"><span>03</span>Dichtheitsmessung<small>5–10 s</small></div><div class="track-fill" :style="{width:progress+'%'}"></div></div>
      <svg class="pressure-chart" viewBox="0 0 610 176" role="img" aria-label="Druckverlauf von null bis zehn Sekunden"><defs><linearGradient id="vp-pressure-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#1458d9" stop-opacity=".16"/><stop offset="100%" stop-color="#1458d9" stop-opacity=".01"/></linearGradient></defs><rect x="312" y="17" width="270" height="130" fill="#f0f7f9"/><g v-for="n in [0,2,4,6]" :key="n"><path :d="`M42 ${147-n/6.5*120}H582`" stroke="#dce5eb" stroke-width=".7"/><text x="30" :y="151-n/6.5*120" text-anchor="end">{{n}}</text></g><g v-for="n in [0,2,4,6,8,10]" :key="'t'+n"><text :x="42+n/10*540" y="167" text-anchor="middle">{{n}} s</text></g><text x="14" y="14">bar</text><text x="574" y="29" text-anchor="end" class="chart-zone">Messfenster</text><path v-if="chartPath" :d="chartPath+` L${42+elapsed/10*540},147 L42,147 Z`" fill="url(#vp-pressure-fill)"/><path v-if="chartPath" :d="chartPath" fill="none" :stroke="stage==='failed'?'#d14a35':'#1458d9'" stroke-width="2.6" stroke-linejoin="round"/></svg>
    </div>
  </section>
</template>

<style scoped>
.valve-lab{font-family:Inter,Arial,sans-serif;color:#183144;display:grid;gap:18px;width:100%;min-width:0}.valve-lab *{box-sizing:border-box}.lab-workspace{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:18px}.scene-panel{position:relative;min-width:0;min-height:530px;border:1px solid #d2dfe7;border-radius:8px;overflow:hidden;background:#e8eef3}.scene-title{position:absolute;top:23px;left:25px;right:23px;z-index:1;display:flex;justify-content:space-between;align-items:flex-start;pointer-events:none}.eyebrow{display:block;font-size:11px;line-height:1.4;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#456477}.scene-title h2{font-size:23px;letter-spacing:-.7px;margin:6px 0;color:#112e40}.simulation-label{font-size:10px;background:#d9e5ed;color:#345468;padding:6px 9px;border-radius:4px;font-weight:700;text-transform:uppercase;letter-spacing:.07em}.scene-viewport{height:530px;touch-action:none}.scene-viewport :deep(canvas){display:block;width:100%;height:100%}.scene-tools{position:absolute;left:22px;bottom:62px;display:flex;align-items:center;gap:7px}.valve-lab button{font:inherit;cursor:pointer;border:1px solid #c8d7e1;background:#fff;color:#244355;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;gap:8px;font-size:12px;font-weight:650;transition:background .15s,border-color .15s}.valve-lab button:focus-visible{outline:3px solid #7fa8f0;outline-offset:3px}.valve-lab button:disabled{opacity:.45;cursor:not-allowed}.valve-lab button:hover:not(:disabled){background:#eaf0fa;border-color:#6585a0}.valve-lab button svg{height:16px;width:16px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.scene-tools button{padding:9px 11px;box-shadow:0 2px 5px #16374d08}.scene-tools button.selected{background:#dce8ff;border-color:#1458d9;color:#1648a2}.scene-tools>span{font-size:10px;color:#547185;margin-left:5px}.scene-caption{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:space-between;padding:14px 22px;background:#f9fbfccc;border-top:1px solid #cedbe5;color:#526e80;font-size:11px}.scene-caption span:first-child{font-weight:700;color:#284658}.control-panel{border:1px solid #d5e0e7;border-radius:8px;background:white;padding:21px;display:flex;flex-direction:column;gap:18px}.control-heading{display:grid;gap:7px}.control-heading strong{font-size:20px;letter-spacing:-.4px}.control-heading>span:last-child{font-size:12px;color:#69808f}.state-banner{display:grid;gap:9px;background:#ecf3ff;border-left:3px solid #1458d9;border-radius:3px;padding:15px}.state-banner>span{font-size:12px;font-weight:700;color:#164da3}.state-banner strong{font-size:35px;font-variant-numeric:tabular-nums;letter-spacing:-1.5px;line-height:1}.state-banner small{font-size:14px;letter-spacing:0;font-weight:500;color:#4b6e8f}.state-banner.passed{background:#e8f7f0;border-color:#128563}.state-banner.passed>span{color:#107052}.state-banner.failed{background:#fff0e9;border-color:#cc4a2a}.state-banner.failed>span{color:#a8381c}.test-facts{display:grid;gap:10px;font-size:11px}.test-facts>div{display:flex;justify-content:space-between;gap:10px}.test-facts span{color:#6a7e8c}.test-facts strong{font-weight:650}.specimen-selector{border:0;padding:0;margin:1px 0 0}.specimen-selector legend{font-size:11px;font-weight:700;margin-bottom:9px}.specimen-selector>div{display:grid;grid-template-columns:1fr 1fr}.specimen-selector button{font-size:10px;padding:9px 5px;border-radius:0}.specimen-selector button:first-child{border-radius:4px 0 0 4px}.specimen-selector button:last-child{border-radius:0 4px 4px 0;border-left:0}.specimen-selector button.active{background:#e5edff;color:#164da3;border-color:#3169cb}.main-controls{display:flex;gap:8px}.main-controls .primary{background:#1458d9;color:#fff;border-color:#1458d9;padding:12px 13px;flex:1}.main-controls .primary:hover:not(:disabled){background:#1047b4;color:white}.main-controls .reset{width:42px}.guard-button{padding:10px;width:100%;justify-content:space-between!important;margin-top:-9px}.guard-hint{font-size:11px;color:#8a571b;margin: -5px 0 0;line-height:1.5}.test-result{border-top:1px solid #e2e9ee;padding-top:14px;display:grid;gap:7px;font-size:11px;line-height:1.5}.test-result strong{font-size:12px}.measurement-panel{border:1px solid #d5e0e7;border-radius:8px;background:white;padding:20px 24px 9px}.measurement-header{display:flex;align-items:center;justify-content:space-between}.measurement-header h3{margin:5px 0 0;font-size:18px;letter-spacing:-.4px}.measurement-time{display:flex;gap:20px;align-items:center}.measurement-time strong{font-size:20px;font-variant-numeric:tabular-nums;letter-spacing:-.4px}.measurement-time strong span{font-size:12px;color:#768c9b;font-weight:500}.measurement-time button{border:0;background:#eef3f7;padding:8px;font-size:10px}.phase-track{position:relative;display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin:20px 0 8px;padding-bottom:11px;border-bottom:3px solid #e7eef3}.phase-track>div:not(.track-fill){display:flex;align-items:center;gap:8px;font-size:11px;font-weight:650;color:#728796}.phase-track>div>span{font-size:10px;border:1px solid #d5e0e7;padding:4px 5px;border-radius:3px;color:#728796}.phase-track small{margin-left:auto;font-size:9px;font-weight:400;color:#8a9ca8}.phase-track>div.current{color:#1458d9}.phase-track>div.current>span{background:#1458d9;color:white;border-color:#1458d9}.phase-track>div.done{color:#10775c}.phase-track>div.done>span{background:#e8f5ef;color:#10775c;border-color:#c5e3d5}.track-fill{position:absolute;bottom:-3px;left:0;background:#1458d9;height:3px;transition:width .1s linear}.pressure-chart{width:100%;height:160px;display:block}.pressure-chart text{font-family:Inter,Arial,sans-serif;font-size:9px;fill:#77909f}.pressure-chart .chart-zone{font-size:8px;fill:#608b99;letter-spacing:.3px}.scene-fallback{position:absolute;inset:120px 40px auto;background:white;padding:20px;border-radius:6px;font-size:13px;line-height:1.6;max-width:430px}@media(min-width:1500px){.scene-panel,.scene-viewport{min-height:620px;height:620px}.lab-workspace{grid-template-columns:minmax(0,1fr) 310px}}@media(max-width:1000px){.lab-workspace{grid-template-columns:minmax(0,1fr) 255px;gap:12px}.control-panel{padding:16px}.scene-tools>span{display:none}.scene-title h2{font-size:19px}.scene-caption span:last-child{display:none}}@media(max-width:720px){.lab-workspace{grid-template-columns:1fr}.scene-panel{min-height:440px}.scene-viewport{height:440px}.control-panel{display:grid;grid-template-columns:1fr 1fr;gap:16px}.control-heading,.state-banner{align-self:start}.test-facts,.specimen-selector,.test-result{grid-column:1/-1}.main-controls,.guard-button{align-self:start;margin:0}.scene-title{top:18px;left:18px}.scene-title h2{font-size:18px}.simulation-label{font-size:8px}.measurement-panel{padding:16px 12px 8px}.phase-track{gap:8px}.phase-track>div:not(.track-fill){font-size:9px;gap:5px}.phase-track small{display:none}.measurement-time{gap:8px}.measurement-time strong{font-size:17px}.scene-tools{left:16px}.scene-caption{padding:13px 16px}}
</style>

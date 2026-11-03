// Native Chrome DevTools smoke test; no Playwright and no injected application state.
import {spawn} from 'node:child_process'
import {mkdtemp,rm,writeFile} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import assert from 'node:assert/strict'
const base=process.env.LCC_URL||'http://localhost:5206',port=9333
const profile=await mkdtemp(join(tmpdir(),'lcc-browser-'))
const chrome=spawn(process.env.CHROME||'/opt/google/chrome/chrome',['--headless=new','--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-extensions','--disable-background-networking','--no-first-run',`--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore'})
let socket,sequence=0;const pending=new Map(),errors=[]
const delay=ms=>new Promise(r=>setTimeout(r,ms))
async function until(fn,description){for(let i=0;i<100;i++){try{const value=await fn();if(value)return value}catch{}await delay(100)}throw Error('UI condition failed: '+description)}
function call(method,params={}){const id=++sequence;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const response=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(response.exceptionDetails)throw Error(response.exceptionDetails.exception?.description||response.exceptionDetails.text);return response.result.value}
async function navigate(path,heading){await call('Page.navigate',{url:base+path});await until(()=>evaluate(`document.querySelector('h1')?.textContent===${JSON.stringify(heading)}`),path)}
async function screenshot(name){const shot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(tmpdir(),name),Buffer.from(shot.data,'base64'))}
try{
 const tabs=await until(async()=>{try{return await(await fetch(`http://127.0.0.1:${port}/json/list`)).json()}catch{return null}},'Chrome starts')
 socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject})
 socket.onmessage=e=>{const message=JSON.parse(e.data);if(message.id){const job=pending.get(message.id);pending.delete(message.id);if(job)message.error?job.reject(message.error):job.resolve(message.result)}else if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.exception?.description||message.params.exceptionDetails.text);else if(message.method==='Network.responseReceived'&&message.params.response.status>=400)errors.push(message.params.response.status+' '+message.params.response.url)}
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:1,mobile:false})
 await navigate('/lcc/moon','Moon simulation')
 await until(()=>evaluate("Boolean(document.querySelector('.moon-canvas canvas'))"),'Scene initializes')
 assert.equal(await evaluate("Boolean(document.querySelector('.scene-fallback'))"),false)
 const launch=await evaluate("(()=>{const r=document.querySelector('.presentation-launch').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
 const started=Date.now();await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...launch});await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...launch})
 await until(()=>evaluate("document.fullscreenElement?.classList.contains('moon-view')"),'Scene enters real fullscreen')
 await delay(1500)
 assert.equal(await evaluate("document.querySelector('.cinematic-overlay').classList.contains('is-waiting')"),true)
 assert.equal(await evaluate("Boolean(document.querySelector('.science-callout'))"),false)
 assert.equal(await evaluate("Boolean(document.querySelector('.moon-view button'))"),false)
 await until(()=>evaluate("Number(document.querySelector('.moon-view').dataset.presentationTime)>=0"),'Five-second lead-in completes')
 assert.ok(Date.now()-started>=4950,'No playback before five seconds')
 await until(()=>evaluate("document.querySelector('.science-callout h2')?.textContent==='THE MOON'"),'Opening callout')
 await until(()=>evaluate("document.querySelector('.cinematic-caption')?.textContent==='The Moon.'"),'Opening subtitle')
 console.log(await evaluate("({time:document.querySelector('.moon-view').dataset.presentationTime,caption:document.querySelector('.cinematic-caption')?.textContent})"))
 assert.equal(await evaluate("document.querySelector('.cinematic-caption')?.textContent"),'The Moon.')
 await screenshot('lcc-presentation-opening.png')
 // After checking the real lead-in, advance Chrome’s clock to inspect each chapter.
 await call('Emulation.setVirtualTimePolicy',{policy:'pause'})
 for(const [at,title,file]of [[43,'LUNAR CHARGE CONTROL','suit'],[67,'SURFACE CONTACT','boots'],[92,'PLASMA ENVIRONMENT','plasma'],[155,'ELECTRON EMITTER','emitter'],[182,'NO UNCONTROLLED SPARK','spark'],[256,'LUNAR CHARGE CONTROL','ending']]){
  const current=Number(await evaluate("document.querySelector('.moon-view').dataset.presentationTime"))
  await call('Emulation.setVirtualTimePolicy',{policy:'advance',budget:Math.max(100,(at-current)*1000),maxVirtualTimeTaskStarvationCount:100})
  await until(()=>evaluate(`Number(document.querySelector('.moon-view').dataset.presentationTime)>=${at-.2}`),'Chapter clock: '+file)
  await until(()=>evaluate(file==='ending'?"Boolean(document.querySelector('.cinematic-title'))":`[...document.querySelectorAll('.science-callout:not(.callout-leave-active) h2')].some(e=>e.textContent===${JSON.stringify(title)})`),'Chapter caption: '+file)
  await delay(1500)
  const observed=await evaluate("({time:document.querySelector('.moon-view').dataset.presentationTime,title:document.querySelector('.science-callout:not(.callout-leave-active) h2')?.textContent,ending:!!document.querySelector('.cinematic-title')})")
  assert.equal(file==='ending'?observed.ending:observed.title,file==='ending'?true:title)
  if(file==='spark')assert.equal(await evaluate("Boolean(document.querySelector('.spark-prohibition'))"),true)
  console.log(file,observed)
  await screenshot('lcc-presentation-'+file+'.png')
 }
 await call('Emulation.setVirtualTimePolicy',{policy:'advance'})
 await evaluate('document.exitFullscreen()')
 await until(()=>evaluate("!document.fullscreenElement&&Boolean(document.querySelector('.presentation-launch'))"),'Exit restores interactive scene')
 assert.deepEqual(errors,[])
 console.log(JSON.stringify({fullscreen:true,leadInSeconds:5,errors},null,2))
}finally{
 socket?.close();chrome.kill('SIGTERM');await delay(500);await rm(profile,{recursive:true,force:true})
}

// Native Chrome DevTools smoke test; no Playwright and no injected application state.
import {spawn} from 'node:child_process'
import {mkdtemp,rm,writeFile} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import assert from 'node:assert/strict'
const base=process.env.LCC_URL||'http://localhost:5206',port=9332
const runName='LCC-Smoke '+crypto.randomUUID()
const testRow=`[...document.querySelectorAll('.lcc-records tbody tr')].find(row=>row.textContent.includes(${JSON.stringify(runName)}))`
const profile=await mkdtemp(join(tmpdir(),'lcc-browser-'))
const chrome=spawn(process.env.CHROME||'/opt/google/chrome/chrome',['--headless=new','--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-extensions','--disable-background-networking','--no-first-run',`--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,'about:blank'],{stdio:'ignore'})
let socket,sequence=0;const pending=new Map(),errors=[],binary=[]
const delay=ms=>new Promise(r=>setTimeout(r,ms))
async function until(fn,description){for(let i=0;i<100;i++){try{const value=await fn();if(value)return value}catch{}await delay(100)}throw Error('UI condition failed: '+description)}
function call(method,params={}){const id=++sequence;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const response=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(response.exceptionDetails)throw Error(response.exceptionDetails.exception?.description||response.exceptionDetails.text);return response.result.value}
const visible=text=>`[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)})`
async function clickText(text){assert.ok(await evaluate(`(()=>{const b=${visible(text)};if(!b||b.disabled)return false;b.click();return true})()`),'Clickable '+text)}
async function clickLabel(label){await until(()=>evaluate(`(()=>{const b=document.querySelector('[aria-label="${label}"]');if(!b||b.disabled)return false;b.click();return true})()`),'Clickable '+label)}
async function navigate(path,heading){await call('Page.navigate',{url:base+path});await until(()=>evaluate(`document.querySelector('h1')?.textContent===${JSON.stringify(heading)}`),path)}
async function englishUI(){
 assert.equal(await evaluate('document.documentElement.lang'),'en');
 const text=await evaluate(`(()=>{const root=document.body.cloneNode(true);root.querySelectorAll('script,style,.message,.thread-open,.lcc-records tbody,.cache-item,.voice-row strong,.table-panel tbody').forEach(e=>e.remove());return root.textContent+' '+[...root.querySelectorAll('[title],[aria-label],[placeholder]')].map(e=>[e.title,e.getAttribute('aria-label'),e.getAttribute('placeholder')].join(' ')).join(' ')})()`);
 assert.ok(!/\b(Prüfstand|Prüfung|Versuch|Versuchsparameter|Modell|gespeichert|Zur Übersicht|Schutzhaube|Vorbereitung|Anzug|Sprachausgabe|Stimmenverwaltung)\b/u.test(text),'English UI contains no German labels');
}
async function screenshot(name){const shot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(tmpdir(),name),Buffer.from(shot.data,'base64'))}
try{
 const tabs=await until(async()=>{try{return await(await fetch(`http://127.0.0.1:${port}/json/list`)).json()}catch{return null}},'Chrome starts')
 socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject})
 socket.onmessage=e=>{const message=JSON.parse(e.data);if(message.id){const job=pending.get(message.id);pending.delete(message.id);if(job)message.error?job.reject(message.error):job.resolve(message.result)}else if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.exception?.description||message.params.exceptionDetails.text);else if(message.method==='Network.webSocketFrameSent')binary.push(message.params.response.opcode);else if(message.method==='Network.responseReceived'&&message.params.response.status>=400)errors.push(message.params.response.status+' '+message.params.response.url)}
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setDeviceMetricsOverride',{width:1600,height:1100,deviceScaleFactor:1,mobile:false})
 await navigate('/','Lunar Charge Control');assert.equal(await evaluate("document.querySelectorAll('.lcc-mode-card').length"),7);await screenshot('lcc-overview.png')
 const modes={plasma:'Plasma test bench',tribo:'Triboelectric test bench',harvester:'Energy harvester',emitter:'Electron emitter',discharge:'Discharge test bench',system:'Integrated system',moon:'Moon simulation'}
 for(const [mode,title]of Object.entries(modes)){
  await navigate('/lcc/'+mode,title)
  await clickLabel('Calculate to completion')
  await until(()=>evaluate("document.querySelector('.metric-status')?.textContent==='Calculated'||document.querySelector('.experiment-clock')?.textContent.startsWith('120.00')"),'Calculation completes: '+mode)
  await englishUI();
  const clock=await evaluate("document.querySelector('.experiment-clock').textContent");assert.ok(!clock.startsWith('0.00'),'Time advances: '+mode)
  assert.equal(await evaluate("document.querySelectorAll('.lcc-chart path').length>0"),true)
  if(mode==='discharge'){
   await screenshot('lcc-discharge.png')
   await evaluate(`(()=>{const input=document.querySelector('[aria-label=\"Experiment name\"]');input.value=${JSON.stringify(runName)};input.dispatchEvent(new Event('input',{bubbles:true}))})()`)
   await clickLabel('Save experiment');await until(()=>evaluate("document.querySelector('.lcc-notice')?.textContent.includes('Experiment saved')"),'Run saved over binary bus')
   await clickText('Experiment runs');await until(()=>evaluate(`Boolean(${testRow})`),'Saved run listed')
   await evaluate(`${testRow}.querySelector('button[title="Compare with current experiment"]').click()`)
   await until(()=>evaluate("Boolean(document.querySelector('.comparison-note'))"),'Saved comparison displayed')
   await clickText('Model & balance');assert.equal(await evaluate("document.querySelector('.lcc-model').textContent.includes('Energy balance residual')"),true)
   await clickText('Experiment runs');await evaluate(`${testRow}.querySelector('button[title="Restore parameters"]').click()`)
   await until(()=>evaluate("document.querySelector('.experiment-clock')?.textContent.startsWith('0.00')"),'Saved parameters restored')
   await clickText('Experiment runs');await evaluate(`${testRow}.querySelector('button[title="Delete experiment"]').click()`)
   await until(()=>evaluate(`!(${testRow})`),'Test run deleted')
  }
  if(mode==='moon'){
   await until(()=>evaluate("Boolean(document.querySelector('.moon-canvas canvas'))"),'Moon WebGL canvas')
   await clickText('Space suit');await clickText('Multilayer sole');await delay(1400);await screenshot('lcc-moon-component.png')
   await evaluate("document.querySelector('.scene-bottom .button').click()")
   await until(()=>evaluate("location.pathname==='/lcc/tribo'"),'Component opens matching bench')
   assert.equal(await evaluate("document.querySelector('.back').textContent.trim()"),'Back to Moon simulation')
   await evaluate("document.querySelector('.back').click()")
   await until(()=>evaluate("document.querySelector('h1')?.textContent==='Moon simulation'&&document.querySelector('.experiment-clock')?.textContent.startsWith('120.00')"),'Parent EVA time restored')
   await until(()=>evaluate("document.querySelector('.component-picker .active')?.textContent==='Multilayer sole'"),'Parent component view restored')
  }
 }
 await navigate('/','Lunar Charge Control');await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await delay(150)
 assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Mobile overview stays within viewport')
 await screenshot('lcc-mobile.png')
 await call('Emulation.setDeviceMetricsOverride',{width:1600,height:1100,deviceScaleFactor:1,mobile:false})
 const legacy={'/shopfloor':'Shopfloor overview','/assistant':'Voice assistant','/protocols':'Inspection reports','/knowledge':'Test procedure FAQ','/admin':'Settings','/admin/voices':'Voice management','/admin/cache':'Response cache'};
 for(const [path,title] of Object.entries(legacy)){await navigate(path,title);await englishUI();if(path==='/knowledge')await until(()=>evaluate("document.querySelector('.faq-entry')?.textContent.includes('How do I start the test?')"),'English FAQ seeds in installed database')}
 await call('Page.navigate',{url:base+'/machines/valve-leak-test'});await until(()=>evaluate("Boolean(document.querySelector('.insert-button'))"),'Valve station retained')
 assert.ok(await evaluate("document.querySelector('.main-controls button').disabled"),'Valve cannot start empty')
 await clickText('Insert valve');await clickText('Close safety guard')
 assert.equal(await evaluate("document.querySelector('.main-controls button').disabled"),false)
 await englishUI()
 assert.ok(binary.length>0&&binary.every(op=>op===2),'Application WebSocket frames are binary')
 assert.deepEqual(errors,[])
 console.log(JSON.stringify({routes:Object.keys(modes),binaryFrames:binary.length,errors,screenshots:['/tmp/lcc-overview.png','/tmp/lcc-discharge.png','/tmp/lcc-moon-component.png','/tmp/lcc-mobile.png']},null,2))
}finally{
 if(socket?.readyState===WebSocket.OPEN){try{await call('Browser.close')}catch{}}
 chrome.kill('SIGTERM');await delay(300);await rm(profile,{recursive:true,force:true})
}

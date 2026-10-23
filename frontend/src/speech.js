import {reactive} from 'vue'
import {rpc,notify,onDisconnect,data} from './transport'
export const speech=reactive({listening:false,starting:false,phase:'idle',playing:false,blocked:false,turn:'',level:0})
let context,microphone,input,node,mute,session='',output=null,nextTime=0,sources=new Set(),onError=()=>{},onInterrupt=()=>{},rows=()=>[]
let talking=false,voiced=0,silence=0,noise=.003,startAttempt=0
export function configureSpeech(options){onError=options.error;onInterrupt=options.interrupt;rows=options.rows}
export async function unlockAudio(){
 if(!context||context.state==='closed')context=new AudioContext()
 if(context.state==='suspended')await context.resume()
 speech.blocked=context.state!=='running'
}
export function stopOutput(){
 const old=[...sources];sources.clear();output=null;nextTime=0;speech.playing=false;speech.blocked=false
 for(const source of old){source.onended=null;try{source.stop()}catch{}source.disconnect()}
}
export function beginTurn(){
 speech.turn=crypto.randomUUID();stopOutput();onInterrupt()
 notify('response.interrupt',{turn:speech.turn})
 return speech.turn
}
export function interruptResponse(){beginTurn();speech.phase=speech.listening?'listening':'idle'}
function finishOutput(){
 if(!output?.ended||sources.size)return
 const completed=output;output=null;speech.playing=false
 if(completed.audioId)rpc('audio.played',{tid:completed.tid,text:completed.audioId}).catch(e=>onError(e.message))
}
export function receiveAudio(frame){
 if(frame.op==='audio.start'){
  stopOutput();output={id:frame.stream,tid:frame.tid,audioId:data(frame.rows?.[0]||{}).audio_id,rate:frame.rate,ended:false}
  speech.playing=true
  if(!context||context.state!=='running')speech.blocked=true
  nextTime=(context?.currentTime||0)+.06
  return
 }
 if(!output||output.id!==frame.stream)return
 if(frame.op==='audio.end'){output.ended=true;finishOutput();return}
 if(frame.op!=='audio.chunk'||!frame.audio?.length)return
 if(!context){context=new AudioContext();nextTime=context.currentTime+.06}
 const view=new DataView(frame.audio.buffer,frame.audio.byteOffset,frame.audio.byteLength)
 const buffer=context.createBuffer(1,frame.audio.byteLength/2,output.rate||22050),channel=buffer.getChannelData(0)
 for(let i=0;i<channel.length;i++)channel[i]=view.getInt16(i*2,true)/32768
 const source=context.createBufferSource();source.buffer=buffer;source.connect(context.destination);sources.add(source)
 source.onended=()=>{sources.delete(source);source.disconnect();finishOutput()}
 nextTime=Math.max(nextTime,context.currentTime+.025);source.start(nextTime);nextTime+=buffer.duration
}
function consume(buffer){
 if(!speech.listening)return
 const samples=new Int16Array(buffer);let energy=0
 for(const sample of samples)energy+=sample*sample
 const rms=Math.sqrt(energy/samples.length)/32768;speech.level=Math.min(1,rms*8)
 const active=rms>Math.max(.014,Math.min(.04,noise*3))
 if(active){voiced++;silence=0;if(!talking&&voiced>=1){talking=true;beginTurn();speech.phase='speaking'}}
 else{voiced=0;silence++;if(!talking)noise=noise*.95+rms*.05;if(talking&&silence>=7){talking=false;speech.phase='transcribing'}}
 try{notify('voice.chunk',{stream:session,turn:speech.turn,audio:new Uint8Array(buffer),rows:rows()})}
 catch(e){stopVoice();onError(e.message)}
}
export async function startVoice(tid){
 if(speech.listening||speech.starting)return
 const attempt=++startAttempt;speech.starting=true
 try{
  // Resume audio during the click gesture, before requesting microphone permission.
  await unlockAudio()
  const acquired=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}})
  if(attempt!==startAttempt){acquired.getTracks().forEach(t=>t.stop());return}
  microphone=acquired
  await context.audioWorklet.addModule('/pcm-capture.js')
  if(attempt!==startAttempt){microphone.getTracks().forEach(t=>t.stop());return}
  session=crypto.randomUUID();beginTurn()
  await rpc('voice.start',{tid,stream:session,rate:16000,turn:speech.turn})
  if(attempt!==startAttempt)return
  input=context.createMediaStreamSource(microphone);node=new AudioWorkletNode(context,'pcm-capture');mute=context.createGain();mute.gain.value=0
  node.port.onmessage=e=>consume(e.data)
  input.connect(node);node.connect(mute);mute.connect(context.destination)
  talking=false;voiced=silence=0;noise=.003;speech.listening=true;speech.phase='listening'
  microphone.getAudioTracks()[0].onended=()=>stopVoice()
 }catch(e){stopVoice();onError(e.name==='NotAllowedError'?'Mikrofonzugriff wurde nicht erlaubt.':e.message||'Spracheingabe nicht verfügbar.')}
 finally{if(attempt===startAttempt)speech.starting=false}
}
export function stopVoice(){
 ++startAttempt;speech.starting=false;speech.listening=false;speech.phase='idle';speech.level=0
 if(node)node.port.onmessage=null
 node?.disconnect();input?.disconnect();mute?.disconnect();node=input=mute=null
 const tracks=microphone?.getTracks()||[];microphone=null
 for(const track of tracks){track.onended=null;track.stop()}
 speech.turn=crypto.randomUUID()
 try{notify(session?'voice.stop':'response.interrupt',{stream:session,turn:speech.turn})}catch{}
 session='';stopOutput();onInterrupt()
}
onDisconnect(()=>stopVoice())
window.addEventListener('pagehide',stopVoice)

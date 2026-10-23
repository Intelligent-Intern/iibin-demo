import {reactive} from 'vue'
import {rpc,onFrame,data} from './transport'
export const state=reactive({models:[],threads:[],tid:localStorage.getItem('werkraum-thread')||'',messages:[],sending:false,notice:'',recording:false,voice:'thorsten',machine:null,pendingAction:'',lastAudio:null,audioBlocked:false})
export function notice(text){state.notice=text;clearTimeout(notice.timer);notice.timer=setTimeout(()=>state.notice='',5500)}
export async function bootstrap(){try{const r=await rpc('bootstrap');state.models=r.rows||[];state.voice=r.voice;await refreshThreads()}catch(e){notice(e.message)}}
export async function refreshThreads(){const r=await rpc('threads.list');state.threads=r.rows||[];if(state.tid&&!state.threads.some(t=>t.id===state.tid)){state.tid='';state.messages=[];localStorage.removeItem('werkraum-thread')}}
export async function newThread(){const r=await rpc('threads.create');state.threads=r.rows||[];await openThread(r.tid)}
export async function openThread(tid){state.tid=tid;localStorage.setItem('werkraum-thread',tid);const r=await rpc('messages.list',{tid});if(state.tid===tid)state.messages=r.rows||[]}
export async function deleteThread(tid){await rpc('threads.delete',{tid});if(state.tid===tid){state.tid='';state.messages=[];localStorage.removeItem('werkraum-thread')}await refreshThreads()}
export async function send(text){if(!text.trim()||state.sending)return;state.sending=true;try{if(!state.tid)await newThread();const optimistic={id:'pending-'+crypto.randomUUID(),kind:'user',text,values:[]};state.messages.push(optimistic);await rpc('message.send',{tid:state.tid,text,...(state.machine?{rows:[{id:'machine',values:[{key:'pressure',number:state.machine.pressure}]}]}:{})});await refreshThreads()}catch(e){notice(e.message)}finally{state.sending=false}}
let player,url
export function stopAudio(){player?.pause();if(url)URL.revokeObjectURL(url);url=null}
export async function play(bytes,tid='',audioId=''){
 stopAudio();url=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));player=new Audio(url);state.lastAudio={bytes,tid,audioId};state.audioBlocked=false
 player.onended=()=>{if(audioId&&tid)rpc('audio.played',{tid,text:audioId}).catch(e=>notice(e.message))}
 try{await player.play()}catch{state.audioBlocked=true}
}
export async function replay(message){const id=data(message).audio_id;if(!id)return;const r=await rpc('audio.get',{text:id});await play(r.audio,state.tid,id)}
onFrame(frame=>{
 if(frame.op==='message.accepted'&&frame.tid===state.tid){const pending=state.messages.findIndex(m=>m.id.startsWith('pending-'));if(pending>=0)state.messages.splice(pending,1,...(frame.rows||[]));else state.messages.push(...(frame.rows||[]))}
 if(frame.op==='message.reply'){
  if(frame.tid===state.tid)state.messages.push(...(frame.rows||[]))
  for(const action of frame.actions||[])window.dispatchEvent(new CustomEvent('shopfloor-action',{detail:action}))
 }
 if(frame.op==='message.audio'){
  if(frame.tid===state.tid){const m=state.messages.find(m=>m.id===frame.rows?.[0]?.id);if(m)Object.assign(m,frame.rows[0]);play(frame.audio,frame.tid,data(frame.rows?.[0]||{}).audio_id)}
 }
})
export async function recordSpeech(){
 if(state.recording){recordSpeech.recorder?.stop();return}
 let stream
 try{stream=await navigator.mediaDevices.getUserMedia({audio:true});const parts=[];const r=new MediaRecorder(stream);recordSpeech.recorder=r;r.ondataavailable=e=>parts.push(e.data);r.onstop=async()=>{state.recording=false;stream.getTracks().forEach(t=>t.stop());try{const bytes=new Uint8Array(await new Blob(parts).arrayBuffer());const response=await rpc('voice.transcribe',{audio:bytes});if(response.text)await send(response.text);else notice('Keine Sprache erkannt.')}catch(e){notice(e.message)}};r.start();state.recording=true;setTimeout(()=>{if(r.state==='recording')r.stop()},30000)}catch(e){stream?.getTracks().forEach(t=>t.stop());notice('Bitte erlaube den Mikrofonzugriff für die Spracheingabe.')}
}

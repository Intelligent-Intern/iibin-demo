import {reactive} from 'vue'
import {rpc,onFrame,data} from './transport'
import {speech,configureSpeech,beginTurn,startVoice,stopVoice,stopOutput,receiveAudio,unlockAudio} from './speech'
export const state=reactive({models:[],threads:[],tid:localStorage.getItem('werkraum-thread')||'',messages:[],sending:false,notice:'',voice:'thorsten',machine:null,pendingAction:'',lastAudio:null,audioBlocked:false})
export function notice(text){state.notice=text;clearTimeout(notice.timer);notice.timer=setTimeout(()=>state.notice='',5500)}
export async function bootstrap(){try{const r=await rpc('bootstrap');state.models=r.rows||[];state.voice=r.voice;await refreshThreads()}catch(e){notice(e.message)}}
export async function refreshThreads(){const r=await rpc('threads.list');state.threads=r.rows||[];if(state.tid&&!state.threads.some(t=>t.id===state.tid)){stopVoice();state.tid='';state.messages=[];localStorage.removeItem('werkraum-thread')}}
export async function newThread(){stopVoice();const r=await rpc('threads.create');state.threads=r.rows||[];await openThread(r.tid)}
export async function openThread(tid){if(tid!==state.tid)stopVoice();state.tid=tid;localStorage.setItem('werkraum-thread',tid);const r=await rpc('messages.list',{tid});if(state.tid===tid)state.messages=r.rows||[]}
export async function deleteThread(tid){if(tid===state.tid)stopVoice();await rpc('threads.delete',{tid});if(state.tid===tid){state.tid='';state.messages=[];localStorage.removeItem('werkraum-thread')}await refreshThreads()}
function machineRows(){return state.machine?[{id:'machine',values:[{key:'pressure',number:state.machine.pressure},{key:'guardOpen',flag:state.machine.guardOpen},{key:'valveInserted',flag:state.machine.valveInserted},{key:'stage',text:state.machine.stage}]}]:[]}
export async function send(text){
 if(!text.trim()||state.sending)return
 let turn
 state.sending=true
 try{
  await unlockAudio()
  if(!state.tid)await newThread()
  turn=beginTurn();state.sending=true
  const optimistic={id:'pending-'+crypto.randomUUID(),kind:'user',text,values:[]};state.messages.push(optimistic)
  await rpc('message.send',{tid:state.tid,text,turn,rows:machineRows()})
  await refreshThreads()
 }catch(e){if(!turn||turn===speech.turn)notice(e.message)}finally{if(!turn||turn===speech.turn)state.sending=false}
}
let player,url
export function stopAudio(){stopOutput();player?.pause();if(url)URL.revokeObjectURL(url);url=null}
export async function play(bytes,tid='',audioId=''){
 beginTurn();stopAudio();speech.playing=true;url=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));player=new Audio(url);state.lastAudio={bytes,tid,audioId};state.audioBlocked=false
 player.onended=()=>{speech.playing=false;if(audioId&&tid)rpc('audio.played',{tid,text:audioId}).catch(e=>notice(e.message))}
 try{await player.play()}catch{speech.playing=false;state.audioBlocked=true}
}
export async function replay(message){const id=data(message).audio_id;if(!id)return;const r=await rpc('audio.get',{text:id});await play(r.audio,state.tid,id)}
configureSpeech({error:notice,rows:machineRows,interrupt:()=>{player?.pause();state.audioBlocked=false;state.sending=false;state.messages=state.messages.filter(m=>!m.id.startsWith('pending-'))}})
onFrame(frame=>{
 if(frame.turn&&frame.turn!==speech.turn)return
 if(frame.op==='voice.status'){
  if(frame.state==='error'){notice(frame.error);speech.phase='listening'}
  else if(speech.listening)speech.phase=frame.state
 }
 if(frame.op==='message.accepted'&&frame.tid===state.tid){
  const pending=state.messages.findIndex(m=>m.id.startsWith('pending-'))
  if(pending>=0)state.messages.splice(pending,1,...(frame.rows||[]));else state.messages.push(...(frame.rows||[]))
  refreshThreads().catch(e=>notice(e.message))
 }
 if(['message.reply','message.update','message.done'].includes(frame.op)){
  if(frame.tid===state.tid)for(const row of frame.rows||[]){const existing=state.messages.find(m=>m.id===row.id);if(existing)Object.assign(existing,row);else state.messages.push(row)}
  for(const action of frame.actions||[])window.dispatchEvent(new CustomEvent('shopfloor-action',{detail:action}))
 }
 if(frame.op.startsWith('audio.')&&frame.tid===state.tid){
  if(frame.op==='audio.start'){const m=state.messages.find(m=>m.id===frame.rows?.[0]?.id);if(m)Object.assign(m,frame.rows[0])}
  receiveAudio(frame)
 }
})
let voiceStarting=false
export async function recordSpeech(){
 if(speech.listening||speech.starting){stopVoice();return}
 if(voiceStarting)return
 voiceStarting=true
 try{await unlockAudio();if(!state.tid)await newThread();await startVoice(state.tid)}catch(e){notice(e.message)}finally{voiceStarting=false}
}

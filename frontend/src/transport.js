import {reactive} from 'vue'
import {Schema} from '@intelligentintern/iibin'
import fields from '../../shared/frame.json'
export const wire=new Schema(fields)
export const connection=reactive({state:'connecting',sent:0,received:0,error:''})
let socket,opening,pending=new Map(),listeners=new Set(),disconnects=new Set()
export function onDisconnect(fn){disconnects.add(fn);return()=>disconnects.delete(fn)}
export function onFrame(fn){listeners.add(fn);return()=>listeners.delete(fn)}
export async function connect(){
 if(socket?.readyState===WebSocket.OPEN)return
 if(opening)return opening
 opening=new Promise((resolve,reject)=>{
  socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);socket.binaryType='arraybuffer'
  socket.onopen=()=>{connection.state='connected';connection.error='';opening=null;resolve()}
  socket.onerror=()=>{connection.error='Die lokale Verbindung ist nicht erreichbar.';reject(new Error(connection.error))}
  socket.onclose=()=>{connection.state='disconnected';for(const fn of disconnects)fn();opening=null;setTimeout(()=>connect().catch(()=>{}),1500);for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error('Verbindung getrennt'))}pending.clear()}
  socket.onmessage=e=>{if(!(e.data instanceof ArrayBuffer))return;connection.received+=e.data.byteLength;let frame;try{frame=wire.decode(e.data)}catch(error){connection.error=error.message;return}for(const fn of listeners)fn(frame);const p=pending.get(frame.id);if(!p)return;if(frame.op==='error'||frame.op?.endsWith('.result')||(p.finishOnReply&&frame.op==='message.reply')){clearTimeout(p.timer);pending.delete(frame.id);frame.error?p.reject(new Error(frame.error)):p.resolve(frame)}}
 });return opening
}
export async function rpc(op,fields={}){await connect();const id=crypto.randomUUID(),data=wire.encode({id,op,...fields});return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Die Verarbeitung dauert länger als erwartet.'))},180000);pending.set(id,{resolve,reject,timer,finishOnReply:op==='message.send'});connection.sent+=data.byteLength;socket.send(data)})}
export function data(row){return Object.fromEntries((row.values||[]).map(v=>[v.key,v.text??v.number??v.flag]))}

export function notify(op,fields={}){
 if(socket?.readyState!==WebSocket.OPEN)throw new Error('Sprachverbindung getrennt.')
 if(socket.bufferedAmount>128*1024)throw new Error('Die Sprachverbindung ist zu langsam. Bitte erneut starten.')
 const payload=wire.encode({op,...fields});connection.sent+=payload.byteLength;socket.send(payload)
}

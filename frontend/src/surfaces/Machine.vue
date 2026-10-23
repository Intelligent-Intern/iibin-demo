<script setup>
import {ref,watch} from 'vue'
import {MessageSquare,ChevronRight} from 'lucide-vue-next'
import ValveLeakTest from '../../../machines/simulation/valve-leak-test/ValveLeakTest.vue'
import VoiceComposer from '../components/VoiceComposer.vue'
import {state,notice} from '../state'
import {rpc} from '../transport'
const machine=ref(null)
function update(s){state.machine=s}
async function complete(s){try{await rpc('protocols.save',{rows:[{id:'measurement',values:[{key:'pressure',number:s.pressure},{key:'drop',number:6-s.pressure},{key:'duration',number:s.elapsed}]}]});notice(s.result==='pass'?'Prüfung bestanden. Protokoll gespeichert.':'Ventil undicht. Protokoll gespeichert.')}catch(e){notice(e.message)}}
watch([()=>state.pendingAction,machine],([action,target])=>{
 if(!action||!target)return
 const commands={machine_close_start:()=>target.closeAndStart(),machine_abort:()=>target.abortTest(),machine_guard_open:()=>target.setGuard(true),machine_guard_close:()=>target.setGuard(false),machine_insert:()=>target.insertValve(true),machine_remove:()=>target.insertValve(false),machine_start:()=>target.startTest(),machine_pause:()=>target.pauseTest(),machine_reset:()=>target.resetTest(),machine_pressure:()=>notice('Aktueller Prüfdruck: '+(state.machine?.pressure??0).toFixed(2)+' bar')}
 const result=commands[action]?.()
 if(result===false)notice('Die Aktion passt gerade nicht zum Maschinenzustand. Prüfe Ventil, Schutzhaube und Prüfablauf.')
 if(state.pendingAction===action)state.pendingAction=''
},{immediate:true})
</script>
<template><div class="machine-surface"><ValveLeakTest ref="machine" @state="update" @complete="complete"/><div class="machine-voice-bar"><RouterLink to="/assistant" class="text-link"><MessageSquare :size="18"/> Gespräch anzeigen <ChevronRight :size="15"/></RouterLink><VoiceComposer/></div></div></template>

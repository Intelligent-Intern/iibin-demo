<script setup>
import {ref,watch,onUnmounted,nextTick} from 'vue'
import {MessageSquare,ChevronRight} from 'lucide-vue-next'
import ValveLeakTest from '../../../machines/simulation/valve-leak-test/ValveLeakTest.vue'
import VoiceComposer from '../components/VoiceComposer.vue'
import {state,notice} from '../state'
import {rpc} from '../transport'
const machine=ref(null)
function update(s){state.machine=s}
async function complete(s){try{await rpc('protocols.save',{rows:[{id:'measurement',values:[{key:'pressure',number:s.pressure},{key:'drop',number:6-s.pressure},{key:'duration',number:s.elapsed}]}]});notice(s.result==='pass'?'Prüfung bestanden. Protokoll gespeichert.':'Ventil undicht. Protokoll gespeichert.')}catch(e){notice(e.message)}}
watch(()=>state.pendingAction,async action=>{if(!action)return;await nextTick();let ok=true;if(action==='machine_guard_open')ok=machine.value?.setGuard(true);if(action==='machine_guard_close')ok=machine.value?.setGuard(false);if(action==='machine_insert')ok=machine.value?.insertValve(true);if(action==='machine_remove')ok=machine.value?.insertValve(false);if(action==='machine_start')ok=machine.value?.startTest();if(action==='machine_pause')ok=machine.value?.pauseTest();if(action==='machine_reset')machine.value?.resetTest();if(action==='machine_pressure')notice('Aktueller Prüfdruck: '+(state.machine?.pressure??0).toFixed(2)+' bar');if(ok===false)notice('Die Aktion passt gerade nicht zum Maschinenzustand. Prüfe Ventil, Schutzhaube und Prüfablauf.');state.pendingAction=''},{immediate:true})
</script>
<template><div class="machine-surface"><ValveLeakTest ref="machine" @state="update" @complete="complete"/><div class="machine-voice-bar"><RouterLink to="/assistant" class="text-link"><MessageSquare :size="18"/> Gespräch anzeigen <ChevronRight :size="15"/></RouterLink><VoiceComposer/></div></div></template>

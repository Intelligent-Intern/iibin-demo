<script setup>
import {ref,computed} from 'vue'
import {ArrowUp,Mic,MicOff,Square,LoaderCircle} from 'lucide-vue-next'
import {state,send,recordSpeech} from '../state'
import {speech,interruptResponse} from '../speech'
const text=ref('')
const status=computed(()=>speech.playing?'Antwort wird gesprochen':speech.phase==='speaking'?'Sprache wird erfasst':speech.phase==='transcribing'?'Sprache wird erkannt':'Mikrofon aktiv')
function submit(){const value=text.value.trim();if(!value||state.sending)return;text.value='';send(value)}
</script>
<template><div class="voice-composer"><div v-if="speech.listening||speech.starting||speech.playing" class="speech-status" role="status"><span class="speech-level" :style="{'--level':speech.level}" aria-hidden="true"><i/><i/><i/><i/><i/></span><span>{{speech.starting?'Mikrofon wird verbunden':status}}</span><button v-if="speech.playing||speech.phase==='transcribing'" type="button" class="interrupt-button" @click="interruptResponse"><Square :size="13"/> Unterbrechen</button></div><form class="composer" @submit.prevent="submit"><input v-model="text" maxlength="1000" aria-label="Nachricht" :placeholder="speech.listening?'Mikrofon aktiv – sprich einen Befehl oder eine Frage':'Frage oder Befehl eingeben …'"><button type="button" class="icon-button" :class="{'is-recording':speech.listening}" :aria-pressed="speech.listening" :disabled="speech.starting" :title="speech.listening?'Sprachmodus beenden':'Sprachmodus starten'" :aria-label="speech.listening?'Sprachmodus beenden':'Sprachmodus starten'" @click="recordSpeech"><LoaderCircle v-if="speech.starting" class="spin" :size="19"/><MicOff v-else-if="speech.listening" :size="19"/><Mic v-else :size="19"/></button><button type="submit" class="send-button" :disabled="state.sending||!text.trim()" aria-label="Nachricht senden"><LoaderCircle v-if="state.sending" class="spin" :size="18"/><ArrowUp v-else :size="19"/></button></form></div></template>

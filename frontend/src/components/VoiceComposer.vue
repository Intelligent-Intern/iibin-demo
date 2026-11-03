<script setup>
import {ref,computed} from 'vue'
import {ArrowUp,Mic,MicOff,Square,LoaderCircle} from 'lucide-vue-next'
import {state,send,recordSpeech} from '../state'
import {speech,interruptResponse} from '../speech'
const text=ref('')
const status=computed(()=>speech.playing?'Speaking response':speech.phase==='speaking'?'Capturing speech':speech.phase==='transcribing'?'Transcribing speech':'Microphone active')
function submit(){const value=text.value.trim();if(!value||state.sending)return;text.value='';send(value)}
</script>
<template><div class="voice-composer"><div v-if="speech.listening||speech.starting||speech.playing" class="speech-status" role="status"><span class="speech-level" :style="{'--level':speech.level}" aria-hidden="true"><i/><i/><i/><i/><i/></span><span>{{speech.starting?'Connecting microphone':status}}</span><button v-if="speech.playing||speech.phase==='transcribing'" type="button" class="interrupt-button" @click="interruptResponse"><Square :size="13"/> Interrupt</button></div><form class="composer" @submit.prevent="submit"><input v-model="text" maxlength="1000" aria-label="Message" :placeholder="speech.listening?'Microphone active – say a command or ask a question':'Enter a question or command …'"><button type="button" class="icon-button" :class="{'is-recording':speech.listening}" :aria-pressed="speech.listening" :disabled="speech.starting" :title="speech.listening?'End voice mode':'Start voice mode'" :aria-label="speech.listening?'End voice mode':'Start voice mode'" @click="recordSpeech"><LoaderCircle v-if="speech.starting" class="spin" :size="19"/><MicOff v-else-if="speech.listening" :size="19"/><Mic v-else :size="19"/></button><button type="submit" class="send-button" :disabled="state.sending||!text.trim()" aria-label="Send message"><LoaderCircle v-if="state.sending" class="spin" :size="18"/><ArrowUp v-else :size="19"/></button></form></div></template>

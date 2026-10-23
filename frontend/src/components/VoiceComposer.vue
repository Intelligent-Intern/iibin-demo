<script setup>
import {ref} from 'vue'
import {ArrowUp,Mic,Square,LoaderCircle} from 'lucide-vue-next'
import {state,send,recordSpeech} from '../state'
const text=ref('')
function submit(){const value=text.value.trim();if(!value||state.sending)return;text.value='';send(value)}
</script>
<template><form class="composer" @submit.prevent="submit"><input v-model="text" maxlength="1000" aria-label="Nachricht" placeholder="Frag etwas oder sag, was du tun möchtest …"><button type="button" class="icon-button" :class="{'is-recording':state.recording}" :title="state.recording?'Aufnahme beenden':'Spracheingabe starten'" @click="recordSpeech"><Square v-if="state.recording" :size="18"/><Mic v-else :size="19"/></button><button type="submit" class="send-button" :disabled="state.sending||!text.trim()" aria-label="Nachricht senden"><LoaderCircle v-if="state.sending" class="spin" :size="18"/><ArrowUp v-else :size="19"/></button></form></template>

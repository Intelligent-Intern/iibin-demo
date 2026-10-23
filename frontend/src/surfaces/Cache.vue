<script setup>
import {ref,onMounted,onUnmounted} from 'vue'
import {Play,RefreshCw} from 'lucide-vue-next'
import {rpc} from '../transport'
import {notice,play} from '../state'
const rows=ref([]),jobs=ref([]),tab=ref('cache');let timer
async function load(){try{const [a,b]=await Promise.all([rpc('cache.list'),rpc('jobs.list')]);rows.value=a.rows||[];jobs.value=b.rows||[]}catch(e){notice(e.message)}}
async function listen(r){try{const response=await rpc('audio.get',{text:r.id});await play(response.audio)}catch(e){notice(e.message)}}
onMounted(()=>{load();timer=setInterval(load,5000)});onUnmounted(()=>clearInterval(timer))
</script>
<template><div><div class="compact-intro"><div><div class="eyebrow">VERWALTUNG / AUDIO</div><h1>Antwortcache</h1><p>Gespeicherte Sprachantworten und Aufträge zur Erzeugung weiterer Varianten.</p></div><button class="button outline" @click="load"><RefreshCw :size="16"/> Aktualisieren</button></div><div class="tabs"><button :class="{active:tab==='cache'}" @click="tab='cache'">Audiovarianten <span>{{rows.length}}</span></button><button :class="{active:tab==='jobs'}" @click="tab='jobs'">Hintergrundaufträge <span>{{jobs.length}}</span></button></div><div class="panel"><div v-if="tab==='cache'" class="cache-list"><div v-for="r in rows" :key="r.id" class="cache-item"><div><span class="tag">{{r.title}}</span><p>{{r.text}}</p><small>{{r.state==='thorsten'?'Thorsten':'Eigene Stimme'}} · {{r.created}}</small></div><button class="icon-button" @click="listen(r)" title="Antwort abspielen"><Play :size="18"/></button></div><div v-if="!rows.length" class="empty-state"><h3>Keine Audiodateien vorhanden.</h3><p>Die Sprachausgabe benötigt beim ersten Start das Piper-Modell.</p></div></div><div v-else class="cache-list"><div v-for="r in jobs" :key="r.id" class="cache-item"><div><strong>{{r.title}}</strong><p v-if="r.text" class="job-error">{{r.text}}</p><small>{{r.created}}</small></div><span class="tag" :class="r.state==='done'?'success':r.state==='error'?'warning':''">{{{done:'Fertig',queued:'Wartet',running:'In Arbeit',error:'Fehlgeschlagen'}[r.state]||r.state}}</span></div></div></div></div></template>

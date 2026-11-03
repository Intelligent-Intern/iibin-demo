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
<template><div><div class="compact-intro"><div><div class="eyebrow">ADMINISTRATION / AUDIO</div><h1>Response cache</h1><p>Saved speech responses and jobs generating additional variants.</p></div><button class="button outline" @click="load"><RefreshCw :size="16"/> Refresh</button></div><div class="tabs"><button :class="{active:tab==='cache'}" @click="tab='cache'">Audio variants <span>{{rows.length}}</span></button><button :class="{active:tab==='jobs'}" @click="tab='jobs'">Background jobs <span>{{jobs.length}}</span></button></div><div class="panel"><div v-if="tab==='cache'" class="cache-list"><div v-for="r in rows" :key="r.id" class="cache-item"><div><span class="tag">{{r.title}}</span><p>{{r.text}}</p><small>{{r.state==='lessac'?'Lessac':'Custom voice'}} · {{r.created}}</small></div><button class="icon-button" @click="listen(r)" title="Play response"><Play :size="18"/></button></div><div v-if="!rows.length" class="empty-state"><h3>No audio files available.</h3><p>Speech synthesis needs the Piper model on first startup.</p></div></div><div v-else class="cache-list"><div v-for="r in jobs" :key="r.id" class="cache-item"><div><strong>{{r.title}}</strong><p v-if="r.text" class="job-error">{{r.text}}</p><small>{{r.created}}</small></div><span class="tag" :class="r.state==='done'?'success':r.state==='error'?'warning':''">{{{done:'Done',queued:'Queued',running:'Running',error:'Failed'}[r.state]||r.state}}</span></div></div></div></div></template>

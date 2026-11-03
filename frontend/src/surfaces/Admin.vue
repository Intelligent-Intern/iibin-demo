<script setup>
import {ref,onMounted,onUnmounted} from 'vue'
import {Mic,Database,ArrowUpRight,Link,Server} from 'lucide-vue-next'
import {rpc,data} from '../transport'
import {state,notice} from '../state'
let timer
async function load(){try{state.models=(await rpc('bootstrap')).rows||[]}catch(e){notice(e.message)}}
onMounted(()=>{load();timer=setInterval(load,5000)});onUnmounted(()=>clearInterval(timer))
</script>
<template><div><div class="compact-intro"><div><div class="eyebrow">ADMINISTRATION</div><h1>Settings</h1><p>Voices, response cache and model status.</p></div><span class="tag">Local demo · Administrator</span></div><div class="admin-grid"><RouterLink to="/admin/voices" class="admin-tile"><span class="feature-icon teal"><Mic :size="26"/></span><ArrowUpRight class="feature-arrow" :size="20"/><h2>Voices</h2><p>Collect recordings, train Piper and select the response voice.</p></RouterLink><RouterLink to="/admin/cache" class="admin-tile"><span class="feature-icon blue"><Database :size="26"/></span><ArrowUpRight class="feature-arrow" :size="20"/><h2>Response cache</h2><p>Prepared audio, new response variants and background jobs.</p></RouterLink></div><div class="panel model-panel"><div class="panel-heading"><h2>Local models</h2><Server :size="20"/></div><div v-for="m in state.models" :key="m.id" class="model-row"><strong>{{{laya:'Laya · Classification',piper:'Piper · Speech synthesis',whisper:'Whisper Tiny · Speech recognition',qwen:'Qwen 3.5 · Open responses'}[m.title]||m.title}}<small class="model-device">{{{gpu:'NVIDIA GPU',hybrid:'GPU / CPU',cpu:'CPU',standby:'Loaded on request',loading:'Detecting device'}[data(m).device]||''}}</small></strong><span class="model-status" :class="{ready:m.state==='ready'}">{{m.state==='ready'?'Ready':m.state==='loading'?'Loading':m.state==='not_loaded'?'Not loaded':m.state==='working'?'Generating a variant':m.state}}</span></div></div><div class="integration-note"><Link :size="20"/><div><strong>User management and permissions</strong><p>This local demo uses a fixed demo identity. Employees are managed outside this application. Production organization sign-in is not configured.</p></div></div></div></template>

<style scoped>
.model-device{margin-left:9px;font-size:10px;font-weight:400;color:var(--muted)}
</style>

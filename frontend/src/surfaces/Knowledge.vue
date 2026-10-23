<script setup>
import {ref,onMounted,computed} from 'vue'
import {Search,Plus,Minus,AudioLines} from 'lucide-vue-next'
import {rpc} from '../transport'
import {notice} from '../state'
const entries=ref([]),query=ref(''),open=ref('')
const visible=computed(()=>entries.value.filter(f=>(f.title+' '+f.text).toLowerCase().includes(query.value.toLowerCase())))
onMounted(async()=>{try{entries.value=(await rpc('faq.list')).rows||[];open.value=entries.value[0]?.id}catch(e){notice(e.message)}})
</script>
<template><div class="knowledge-surface"><div class="compact-intro"><div><div class="eyebrow">WISSEN AM ARBEITSPLATZ</div><h1>Die richtige Antwort.<br>Direkt zur Hand.</h1><p>Bedienung und Prüfablauf der Ventil-Dichtheitsprüfung.</p></div><label class="search-field"><Search :size="17"/><input v-model="query" placeholder="Eine Frage suchen …" aria-label="FAQ durchsuchen"></label></div><div class="knowledge-layout"><div class="knowledge-aside"><span class="large-number">10</span><h2>Fragen.<br>Klare Antworten.</h2><p>Alle Angaben beziehen sich auf den simulierten Prüfstand VP-01.</p><RouterLink to="/assistant" class="text-link"><AudioLines :size="17"/> Lieber per Sprache fragen</RouterLink></div><div class="panel faq-panel"><article v-for="f in visible" :key="f.id" class="faq-entry"><button :aria-expanded="open===f.id" @click="open=open===f.id?'':f.id"><span>{{f.title}}</span><Minus v-if="open===f.id" :size="17"/><Plus v-else :size="17"/></button><p v-if="open===f.id">{{f.text}}</p></article><div v-if="!visible.length" class="empty-state">Keine passende Frage gefunden.</div></div></div></div></template>

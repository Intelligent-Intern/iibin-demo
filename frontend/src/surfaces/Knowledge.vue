<script setup>
import {ref,onMounted,computed} from 'vue'
import {Search,Plus,Minus,AudioLines} from 'lucide-vue-next'
import {rpc} from '../transport'
import {notice} from '../state'
const entries=ref([]),query=ref(''),open=ref('')
const visible=computed(()=>entries.value.filter(f=>(f.title+' '+f.text).toLowerCase().includes(query.value.toLowerCase())))
onMounted(async()=>{try{entries.value=(await rpc('faq.list')).rows||[];open.value=entries.value[0]?.id}catch(e){notice(e.message)}})
</script>
<template><div class="knowledge-surface"><div class="compact-intro"><div><div class="eyebrow">OPERATION</div><h1>Test procedure FAQ</h1><p>Operation and procedure of the valve leak test.</p></div><label class="search-field"><Search :size="17"/><input v-model="query" placeholder="Search questions …" aria-label="Search FAQ"></label></div><div class="knowledge-layout"><div class="knowledge-aside"><span class="large-number">10</span><h2>FAQ entries</h2><p>All information refers to the simulated VP-01 test bench.</p><RouterLink to="/assistant" class="text-link"><AudioLines :size="17"/> Open voice assistant</RouterLink></div><div class="panel faq-panel"><article v-for="f in visible" :key="f.id" class="faq-entry"><button :aria-expanded="open===f.id" @click="open=open===f.id?'':f.id"><span>{{f.title}}</span><Minus v-if="open===f.id" :size="17"/><Plus v-else :size="17"/></button><p v-if="open===f.id">{{f.text}}</p></article><div v-if="!visible.length" class="empty-state">No matching question found.</div></div></div></div></template>

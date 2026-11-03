<script setup>
import {computed,ref} from 'vue'
const props=defineProps({title:String,samples:Array,fields:Array,comparison:Object})
const selected=ref(null),hidden=ref(new Set())
const traces=computed(()=>props.fields.filter(f=>!hidden.value.has(f.key)))
const all=computed(()=>[...props.samples,...(props.comparison?.samples||[])])
const xmax=computed(()=>Math.max(1,...all.value.map(s=>s.time)))
const bounds=computed(()=>{const values=traces.value.flatMap(f=>all.value.map(s=>(s[f.key]||0)*f.scale));let lo=Math.min(0,...values),hi=Math.max(0,...values);if(lo===hi)hi=lo+1;const pad=(hi-lo)*.08;return [lo-pad,hi+pad]})
const y=v=>174-(v-bounds.value[0])/(bounds.value[1]-bounds.value[0])*142
const path=(rows,field)=>rows.map((s,i)=>`${i?'L':'M'}${(48+s.time/xmax.value*490).toFixed(2)},${y((s[field.key]||0)*field.scale).toFixed(2)}`).join(' ')
const current=computed(()=>selected.value===null?props.samples.at(-1):props.samples.reduce((a,b)=>Math.abs(b.time-selected.value)<Math.abs(a.time-selected.value)?b:a,props.samples[0]))
function point(e){const rect=e.currentTarget.getBoundingClientRect();selected.value=Math.max(0,Math.min(xmax.value,((e.clientX-rect.left)/rect.width*560-48)/490*xmax.value))}
function toggle(key){const next=new Set(hidden.value);next.has(key)?next.delete(key):next.add(key);hidden.value=next}
function format(n){return Math.abs(n)>=1000||Math.abs(n)>0&&Math.abs(n)<.001?n.toExponential(1):n.toFixed(2)}
</script>
<template><section class="lcc-chart"><header><h3>{{title}}</h3><small>{{current?current.time.toFixed(2):'0.00'}} s</small></header><svg viewBox="0 0 560 208" role="img" :aria-label="title+' over time'" @pointermove="point" @pointerleave="selected=null"><g v-for="i in 4" :key="i"><line x1="48" x2="538" :y1="32+(i-1)*142/3" :y2="32+(i-1)*142/3" stroke="#d9e4ed"/><text x="42" :y="36+(i-1)*142/3" text-anchor="end">{{format(bounds[1]-(i-1)*(bounds[1]-bounds[0])/3)}}</text></g><g v-for="f in traces" :key="f.key"><path v-if="comparison" :d="path(comparison.samples,f)" fill="none" :stroke="f.color" stroke-width="1.5" stroke-dasharray="5 4" opacity=".5"/><path :d="path(samples,f)" fill="none" :stroke="f.color" stroke-width="2"/></g><line v-if="selected!==null" :x1="48+selected/xmax*490" :x2="48+selected/xmax*490" y1="28" y2="174" stroke="#657991" stroke-dasharray="3 3"/><text x="48" y="197">0 s</text><text x="538" y="197" text-anchor="end">{{xmax.toFixed(1)}} s</text></svg><div class="chart-legend"><button v-for="f in fields" :key="f.key" :style="{color:f.color,opacity:hidden.has(f.key)?.4:1}" @click="toggle(f.key)"><i :style="{background:f.color}"/>{{f.label}} <strong>{{current?format((current[f.key]||0)*f.scale):'0'}} {{f.unit}}</strong></button></div><small v-if="comparison" class="comparison-note">Dashed: {{comparison.title}}</small></section></template>

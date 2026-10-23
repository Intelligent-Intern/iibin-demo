import {createApp} from 'vue'
import {createRouter,createWebHistory} from 'vue-router'
import App from './App.vue'
import Dashboard from './surfaces/Dashboard.vue'
const Machine=()=>import('./surfaces/Machine.vue')
const Assistant=()=>import('./surfaces/Assistant.vue')
const Protocols=()=>import('./surfaces/Protocols.vue')
const Knowledge=()=>import('./surfaces/Knowledge.vue')
const Admin=()=>import('./surfaces/Admin.vue')
const Voices=()=>import('./surfaces/Voices.vue')
const Cache=()=>import('./surfaces/Cache.vue')
import './style.css'
const router=createRouter({history:createWebHistory(),routes:[{path:'/',component:Dashboard,meta:{title:'Übersicht'}},{path:'/machines/valve-leak-test',component:Machine,meta:{title:'Ventil-Dichtheitsprüfung'}},{path:'/assistant',component:Assistant,meta:{title:'Sprachassistent'}},{path:'/protocols',component:Protocols,meta:{title:'Prüfprotokolle'}},{path:'/knowledge',component:Knowledge,meta:{title:'Wissen & Hilfe'}},{path:'/admin',component:Admin,meta:{title:'Verwaltung'}},{path:'/admin/voices',component:Voices,meta:{title:'Stimmenverwaltung'}},{path:'/admin/cache',component:Cache,meta:{title:'Antwortcache'}},{path:'/:pathMatch(.*)*',redirect:'/'}]})
createApp(App).use(router).mount('#app')

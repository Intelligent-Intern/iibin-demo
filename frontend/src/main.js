import {createApp} from 'vue'
import {createRouter,createWebHistory} from 'vue-router'
import App from './App.vue'
import Dashboard from './surfaces/Dashboard.vue'
import LunarDashboard from './lunar/Dashboard.vue'
const LunarWorkbench=()=>import('./lunar/Workbench.vue')
import './lunar/lunar.css'
const Machine=()=>import('./surfaces/Machine.vue')
const Assistant=()=>import('./surfaces/Assistant.vue')
const Protocols=()=>import('./surfaces/Protocols.vue')
const Knowledge=()=>import('./surfaces/Knowledge.vue')
const Admin=()=>import('./surfaces/Admin.vue')
const Voices=()=>import('./surfaces/Voices.vue')
const Cache=()=>import('./surfaces/Cache.vue')
import './style.css'
const router=createRouter({history:createWebHistory(),routes:[{path:'/',component:LunarDashboard,meta:{title:'Lunar Charge Control',lunar:true}},{path:'/lcc/:mode(moon|plasma|tribo|harvester|emitter|discharge|system)',component:LunarWorkbench,meta:{title:'Lunar Charge Control',lunar:true}},{path:'/shopfloor',component:Dashboard,meta:{title:'Shopfloor'}},{path:'/machines/valve-leak-test',component:Machine,meta:{title:'Valve leak test'}},{path:'/assistant',component:Assistant,meta:{title:'Voice assistant'}},{path:'/protocols',component:Protocols,meta:{title:'Inspection reports'}},{path:'/knowledge',component:Knowledge,meta:{title:'Knowledge & help'}},{path:'/admin',component:Admin,meta:{title:'Administration'}},{path:'/admin/voices',component:Voices,meta:{title:'Voice management'}},{path:'/admin/cache',component:Cache,meta:{title:'Response cache'}},{path:'/:pathMatch(.*)*',redirect:'/'}]})
createApp(App).use(router).mount('#app')

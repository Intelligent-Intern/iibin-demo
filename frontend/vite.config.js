import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
export default defineConfig({plugins:[vue(),tailwindcss()],resolve:{dedupe:["vue","three"]},server:{fs:{allow:[path.resolve('..'),path.resolve('../../iibin-js')]},proxy:{'/ws':{target:'ws://127.0.0.1:5207',ws:true},'/api':'http://127.0.0.1:5207','/health':'http://127.0.0.1:5207'}}})

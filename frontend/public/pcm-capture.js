// Continuous mono PCM16 at 16 kHz; each transferred block contains 100 ms.
class PcmCapture extends AudioWorkletProcessor {
 constructor(){super();this.step=sampleRate/16000;this.phase=0;this.previous=0;this.block=new Int16Array(1600);this.index=0}
 process(inputs){
  const input=inputs[0]?.[0];if(!input)return true
  while(this.phase<input.length){
   const pos=Math.floor(this.phase),fraction=this.phase-pos
   const a=pos<0?this.previous:input[pos],b=input[Math.min(pos+1,input.length-1)]
   this.block[this.index++]=Math.round(Math.max(-1,Math.min(1,a+(b-a)*fraction))*32767)
   if(this.index===1600){this.port.postMessage(this.block.buffer,[this.block.buffer]);this.block=new Int16Array(1600);this.index=0}
   this.phase+=this.step
  }
  this.phase-=input.length;this.previous=input[input.length-1];return true
 }
}
registerProcessor('pcm-capture',PcmCapture)

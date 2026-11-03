// Editorial timeline in seconds, measured after the five-second fullscreen lead-in.
export const LEAD_IN = 5
export const DURATION = 264
export const CUES = [
 [3,'The Moon.'],
 [7,'A world without air. Without mercy. And without a second chance.'],
 [17,'At its southern pole, sunlight disappears into craters that have remained dark for billions of years.'],
 [28,'Here, even a single footstep can become a threat.'],
 [37,'Introducing the next generation of lunar exploration technology.'],
 [45,'Lunar Charge Control.'],
 [52,"An intelligent electrostatic management system, integrated directly into the astronaut’s suit."],
 [60,'Every step across the lunar surface creates friction.'],
 [66,'Every contact with the ground can transfer electrical charge.'],
 [72,'Inside the boots, advanced electrode layers are designed to minimize this buildup while harvesting energy from the motion of walking.'],
 [83,'But the ground is only part of the danger.'],
 [89,'Invisible streams of charged particles surround the astronaut.'],
 [95,'And deep inside the lunar shadows, the natural mechanisms that normally balance electrical charge begin to disappear.'],
 [106,'The suit can become a high-voltage capacitor.'],
 [111,'One hundred thousand volts.'],
 [117,'Waiting for a connection.'],
 [123,'Lunar Charge Control explores a different approach.'],
 [128,'Instead of allowing electrical energy to accumulate unchecked, its harvesting system captures usable energy wherever a controlled transfer is possible.'],
 [143,'Sensors monitor the suit’s electrical state.'],
 [149,'And when negative charge becomes dangerous, a dedicated electron emitter is designed to release excess electrons into space.'],
 [164,'As the astronaut returns to the lander, one final protection remains.'],
 [172,'A controlled discharge interface safely equalizes the electrical potential before physical contact.'],
 [180,'No uncontrolled spark.'],
 [186,'No sudden electrical shock. Just a carefully managed return.'],
 [199,'On Earth, static electricity is an inconvenience.'],
 [206,'On the Moon, it can become a mission-ending threat.'],
 [214,'Our mission is to turn that threat into an opportunity.'],
 [223,'To understand the charge.'],
 [228,'To control the energy.'],
 [237,'And to protect the human being inside the suit.'],
 [248,'Lunar Charge Control.'],
 [253,'Harness the energy. Control the charge. Explore beyond the light.'],
]
export const SHOTS = [
 {at:0,until:17,target:'terrain',title:'THE MOON',detail:'Lunar south pole · Surface environment',offset:[22,12,26]},
 {at:17,until:37,target:'crater',title:'PERMANENT SHADOW',detail:'Low solar elevation · Crater interior',offset:[8,5,12]},
 {at:37,until:60,target:'suit',title:'LUNAR CHARGE CONTROL',detail:'Integrated electrostatic management',offset:[2.8,1.1,4.6]},
 {at:60,until:72,target:'sole',title:'SURFACE CONTACT',detail:'Contact · Separation · Charge transfer',offset:[.9,.28,1.35]},
 {at:72,until:83,target:'sole',title:'MULTILAYER ELECTRODES',detail:'Layered sole · Mechanical energy input',offset:[.56,.1,.82]},
 {at:83,until:95,target:'suit',title:'PLASMA ENVIRONMENT',detail:'Electron collection · Ion collection · Photoemission',offset:[2.8,.6,3.7]},
 {at:95,until:106,target:'suit',title:'SHADOW TRANSITION',detail:'Photoemission stops in shadow',offset:[-2.4,.6,3.6]},
 {at:106,until:123,target:'sensor',title:'ELECTRICAL POTENTIAL',detail:'Capacitive charging · Q = C × V',offset:[.8,.25,1.3]},
 {at:123,until:143,target:'harvester',title:'ENERGY HARVESTER',detail:'Controlled transfer → Electrical storage',offset:[1,.3,-1.65]},
 {at:143,until:149,target:'sensor',title:'POTENTIAL SENSORS',detail:'Suit potential · Environmental reference',offset:[.7,.2,1.1]},
 {at:149,until:164,target:'emitter',title:'ELECTRON EMITTER',detail:'Electron extraction → Escape into the environment',offset:[.9,.2,-1.3]},
 {at:164,until:172,target:'lander',title:'RETURN TO THE LANDER',detail:'Controlled electrical connection',offset:[5,2.5,7]},
 {at:172,until:180,target:'interface',title:'DISCHARGE INTERFACE',detail:'Current limiting · Potential equalization',offset:[1.3,.65,2]},
 {at:180,until:186,target:'interface',title:'NO UNCONTROLLED SPARK',detail:'Controlled current path',offset:[1.1,.4,1.65]},
 {at:186,until:199,target:'lander',title:'MANAGED RETURN',detail:'Charge control through the final connection',offset:[4.5,2,6]},
 {at:199,until:223,target:'suit',title:'LUNAR EXPLORATION',detail:'Environment · Energy · Charge',offset:[3.8,1.4,5]},
 {at:223,until:228,target:'sensor',title:'UNDERSTAND THE CHARGE',detail:'Monitor electrical potential',offset:[1,.3,1.7]},
 {at:228,until:237,target:'storage',title:'CONTROL THE ENERGY',detail:'Harvesting · Storage · Emission',offset:[1,.3,-1.8]},
 {at:237,until:248,target:'suit',title:'PROTECT THE EXPLORER',detail:'Integrated suit systems',offset:[2.2,.9,3.5]},
 {at:248,until:264,target:'hero',title:'LUNAR CHARGE CONTROL',detail:'Harness the energy. Control the charge. Explore beyond the light.',offset:[6,2.5,9]},
]
export function presentationAt(seconds){
 const time=Math.max(0,Math.min(DURATION,seconds))
 const shot=SHOTS.find(s=>time>=s.at&&time<s.until)||SHOTS.at(-1)
 const cue=CUES.findLast(([at])=>at<=time)
 return {time,shot,caption:cue?.[1]||'',cueAt:cue?.[0]??-1,progress:(time-shot.at)/(shot.until-shot.at),spark:time>=180&&time<186,ended:time>=DURATION}
}

# Valve leak-test station

`ValveLeakTest.vue` is the routed surface content; the application owns its page header and back navigation. Requires `vue` and `three`. It contains actual procedural Three.js geometry, OrbitControls, PBR materials, environmental lighting, shadows, a hinged guard, moving clamp, regulator dial, optional cutaway and a pressure graph.

```vue
<ValveLeakTest ref="machine" @state="onState" @complete="onResult" />
```

Exposed methods: `startTest()`, `pauseTest()` (toggles pause), `resetTest()`, `setLeak(boolean)`, `toggleGuard()`, `currentState()`. Commands return `false` when machine prerequisites prevent the action. A running test locks guard and specimen selection. Opening the guard raises the clamp. State events contain `machine`, `stage`, `elapsed` (seconds), `pressure` (bar), `leak`, `guardOpen`, `paused` and `result` (`pass`, `fail`, or null).

Cycle: 3 s pressure buildup, 2 s stabilization, 5 s isolated pressure hold. Nominal pressure 6 bar. Healthy specimen loses 0.015 bar during measurement; defective specimen loses 0.95 bar. Acceptance threshold shown in the UI is 0.10 bar. These are explicitly simulated values for the application, not a validated industrial test procedure.

The component currently owns the local simulation clock. For a shared multi-client machine, replace that clock with authoritative server state; retain the same command methods and state representation. No external assets or network requests are required. All renderer, geometry, texture, material, observer and animation resources are released on unmount.

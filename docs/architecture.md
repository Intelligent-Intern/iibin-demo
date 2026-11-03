# Architecture and integration

## Existing station reviewed

The original application has route-specific Vue surfaces, a shared top header and dashboard back navigation, no application sidebar, and a binary IIBIN WebSocket transport. `machines/simulation/valve-leak-test/ValveLeakTest.vue` owns its local clock, pressure history and machine interlocks. It exposes start/pause/reset, guard and specimen operations; the routed `Machine.vue` wrapper publishes finished reports over the socket. Three.js supplies procedural geometry, PBR finishes, lighting, shadows, OrbitControls and explicit GPU cleanup. There is no separate floorplan host in this repository; the existing Shopfloor application is the integration host.

## LCC integration

The root dashboard is Lunar Charge Control. `/lcc/:mode` provides seven explicit modes; `/shopfloor` retains the former dashboard. Valve geometry and simulation implementation are unchanged.

- `machines/simulation/lunar-charge-control/parameters.js`: parameter definitions, display units, valid ranges, construction choices and scenarios.
- `machines/simulation/lunar-charge-control/engine.js`: pure, browser-independent physics and result records. It runs unchanged in Node tests and the browser worker.
- `frontend/src/lunar/simulation.worker.js`: ordered reset/advance jobs outside the UI thread.
- `frontend/src/lunar/controller.js`: playback scheduling, stale-response protection, binary persistence, downloads.
- `frontend/src/lunar/Workbench.vue`: shared parameter controls, measurements, comparisons, model and balance views.
- `frontend/src/lunar/Chart.vue`: plotted model samples, time cursor, selectable traces and dashed comparison runs.
- `frontend/src/lunar/MoonScene.vue`: Three.js environment, component picking, camera transitions and fullscreen presentation lifecycle. Normal interaction consumes the workbench state; presentation samples a separate deterministic run of the same physics engine and does not alter saved experiments.
- `frontend/src/lunar/scene-detail.js`: procedural suit hardware, lander assemblies, cratered terrain, instanced rocks, footprints and separate symbolic particle species. Geometry, materials and particle textures are disposed when leaving the surface.
- `frontend/src/lunar/presentation.js`: English narration cues, camera chapters, five-second fullscreen lead-in, closing hold and spark timing. Pure timeline lookup is independently tested.
- `frontend/src/lunar/presentation.css`: fullscreen layout, control-free cinematic overlays, animated callout leaders, captions and spark strike-through.
- `frontend/src/lunar/BenchDiagram.vue`: functional diagrams driven by the same calculated samples.
- `backend/lunar.py`: bounded, immutable experiment storage through the existing message dispatcher. Parameterized SQLite writes; no new REST endpoints.

Simulation progress is explicit; the worker does not advance while playback is paused or the document is hidden. Returning to a hidden page does not add hidden wall-clock time. Playback speed changes the rate of requested fixed ticks, not the tick size. Arbitrary scheduling chunks are accumulated to the next fixed tick; the final run state and sample series are independent of browser frame timing.

Opening a component workbench includes an explicit return destination. Returning restores the source experiment parameters, elapsed fixed-clock time and selected component by deterministic recalculation; no background simulation continues on an unmounted page. A new parameter set starts a new experiment. Stored runs include model version, full parameters, signed charge transfers, energy ledger, summary and SI sample series. Restoring a run restores its parameters and displays its recorded series as a comparison. Historical records are never silently recalculated. Deleting a record is explicit. No worker or camera resources survive an unmounted LCC page.

## Transport and runtime

The existing schema's typed rows carry numeric sample values, booleans and phase names. A versioned JSON metadata envelope inside the binary header carries the parameter/ledger structure. Application frames are binary IIBIN. Run operations are `lunar.runs.list`, `.save`, `.get`, `.delete`. Save checks the recognized model/mode, bounded sample count and payload size, finite values, strictly increasing sample times, mandatory quantities and final-summary consistency. This is storage validation, not an independent server-side recalculation of client results.

The default Docker target contains the web bundle, native IIBIN codec and minimal API dependencies. AI and audio dependencies are isolated in the optional `voice` image target and Ollama Compose profile. Existing voice integration is retained without making lunar physics depend on inference or model downloads.

## Verification

`make test` checks analytical capacitance/energy, RC behavior, current limits, emitter direction and failure, isolated-converter invariance, separate tribo charge/generation, plasma equilibrium, all scenarios' conservation and reproducibility, scheduling independence and immutable persistence including malformed-record rejection. `tests/browser-smoke.mjs` uses Chrome's native DevTools protocol against the running production bundle to exercise all seven routes, calculation, saving/restoring/comparing/deleting a test run, component navigation, binary frames, responsive layout and the original valve interlocks.

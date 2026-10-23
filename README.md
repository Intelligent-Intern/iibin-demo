# Werkraum — IIBIN Shopfloor

Vue 3 + Tailwind application, FastAPI binary IIBIN WebSocket backend, native C Python codec, Three.js valve leak-test station. Each surface has its own route and a back link to the dashboard. The machine stays alive across route changes so its guard, inserted valve and running inspection are retained. Voice commands can open/close the guard, insert/remove the valve and start the inspection; “Ich habe das Ventil eingelegt” registers insertion. The insertion button moves the specimen into the fixture. Insertion/removal requires an open guard; starting requires an inserted valve and a closed guard; the guard is locked during a running or paused inspection. No application sidebar.

From this directory:

```sh
make build
make up
make down
```

Open http://localhost:5206. Docker volumes retain conversations, recordings, models, voices, cached audio and inspection reports across `make down`. First startup downloads the CPU models (Laya multilingual, Whisper tiny, Piper Thorsten and Qwen 3.5 2B). Their status is visible under Administration. Network access is needed for those downloads, not for subsequent inference.

The local demo is bound to loopback and uses an explicit demo administrator identity. Employees are not created here. A production identity-provider connection is not configured.

The microphone button opens a continuous 16 kHz mono PCM16 stream over binary IIBIN WebSocket blocks (100 ms each). Speech segments are transcribed on CPU after 650 ms of silence; sustained speech is segmented after 15 seconds. The microphone stays open across replies and route navigation. Speaking again interrupts playback immediately in the browser and cancels the pending response on the server. The Stop response control does the same without closing the microphone; Mic off closes the input and output. Thread changes, disconnection and leaving the page release the microphone. Echo cancellation and noise suppression are requested from the browser. Whisper tiny processes completed speech segments, not live partial transcripts. Laya selects one registered FAQ, navigation or simulation action. Audio replies use Piper and stream cached WAV content as paced PCM blocks into a continuous Web Audio playback queue. Interrupted responses are not registered as fully played. Playback requires an initial user gesture; a visible enable-audio control handles browser restrictions. Playback completion registers the variant against the thread and queues a new Qwen/Piper variant without delaying the reply. Qwen selects an unused, reviewed wording from `content/answer-variants.json` through a closed index schema; model-generated free text is never stored as a playable FAQ answer. Unused reviewed variants take priority. Once all variants have been played in a thread, the least recently played one is reused so voice output remains available. Audio autoplay may require a browser click. The audio cache is shared; thread deletion removes its messages and playback history, not voices or reports.

A custom voice requires your own recordings with matching transcripts. Create a voice in Administration → Voices, record at least 20 different sentences, then start training. Piper CPU fine tuning is a real background process, not instant zero-shot cloning. The initial checkpoint is downloaded from the official Rhasspy Piper checkpoint repository on first training. Quality and training duration depend on your dataset. Job failures are visible in Administration → Answer cache; full training output is retained in the data volume.

Only uploads use HTTP. All application commands, data, transcriptions and audio responses use schema-defined binary WebSocket frames. The socket accepts both `ws://localhost:5206/` and `ws://localhost:5206/ws`. The wire schema is `shared/frame.json`. The independent JS/Python packages live in sibling repositories; the old non-schema JS codecs are available only under the explicit `/legacy` entry point.

# Werkraum — IIBIN Shopfloor

Vue 3 + Tailwind application, FastAPI binary IIBIN WebSocket backend, native C Python codec, Three.js valve leak-test station. Each surface has its own route and a back link to the dashboard. No application sidebar.

From this directory:

```sh
make build
make up
make down
```

Open http://localhost:5206. Docker volumes retain conversations, recordings, models, voices, cached audio and inspection reports across `make down`. First startup downloads the CPU models (Laya multilingual, Whisper tiny, Piper Thorsten and Qwen 3.5 2B). Their status is visible under Administration. Network access is needed for those downloads, not for subsequent inference.

The local demo is bound to loopback and uses an explicit demo administrator identity. Employees are not created here. A production identity-provider connection is not configured.

Speech input is transcribed on CPU. Laya selects one registered FAQ, navigation or simulation action. Audio replies use Piper. Playback completion registers the variant against the thread and queues a new Qwen/Piper variant without delaying the reply. Qwen selects an unused, reviewed wording from `content/answer-variants.json` through a closed index schema; model-generated free text is never stored as a playable FAQ answer. Audio autoplay may require a browser click. The audio cache is shared; thread deletion removes its messages and playback history, not voices or reports.

A custom voice requires your own recordings with matching transcripts. Create a voice in Administration → Voices, record at least 20 different sentences, then start training. Piper CPU fine tuning is a real background process, not instant zero-shot cloning. The initial checkpoint is downloaded from the official Rhasspy Piper checkpoint repository on first training. Quality and training duration depend on your dataset. Job failures are visible in Administration → Answer cache; full training output is retained in the data volume.

Only uploads use HTTP. All application commands, data, transcriptions and audio responses use schema-defined binary WebSocket frames. The wire schema is `shared/frame.json`. The independent JS/Python packages live in sibling repositories; the old non-schema JS codecs are available only under the explicit `/legacy` entry point.

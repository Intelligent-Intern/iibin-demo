FROM node:22-bookworm-slim AS web
WORKDIR /workspace/iibin-js
COPY iibin-js/package*.json ./
RUN npm ci --ignore-scripts
COPY iibin-js/src ./src
COPY iibin-js/tsconfig.json ./
RUN npm run build
WORKDIR /workspace/iibin-demo/frontend
COPY iibin-demo/frontend/package*.json ./
RUN npm ci --ignore-scripts
COPY iibin-demo/frontend .
COPY iibin-demo/shared /workspace/iibin-demo/shared
COPY iibin-demo/content /workspace/iibin-demo/content
COPY iibin-demo/machines /workspace/iibin-demo/machines
RUN npm run build

FROM python:3.12-slim-bookworm AS codec
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY iibin-py /packages/iibin-py
RUN pip wheel --no-cache-dir --no-deps /packages/iibin-py -w /wheels

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
COPY --from=codec /wheels /wheels
COPY iibin-demo/requirements-runtime.txt ./requirements.txt
RUN pip install --no-cache-dir /wheels/*.whl -r requirements.txt
COPY iibin-demo/backend ./backend
COPY iibin-demo/content ./content
COPY iibin-demo/shared ./shared
COPY --from=web /workspace/iibin-demo/frontend/dist ./frontend/dist
RUN useradd --uid 10001 --create-home shopfloor && mkdir -p /data && chown shopfloor:shopfloor /data /app
USER shopfloor
ENV IIBIN_DATA=/data HF_HOME=/data/models/huggingface CUDA_VISIBLE_DEVICES="" CPU_THREADS=4 ENABLE_VOICE=0
EXPOSE 5206
CMD ["uvicorn","backend.app:app","--host","0.0.0.0","--port","5206","--ws-max-size","16777216"]

FROM runtime AS voice
USER root
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake ninja-build ffmpeg libsndfile1 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY iibin-demo/requirements.txt /tmp/voice-requirements.txt
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/voice-requirements.txt
USER shopfloor
ENV ENABLE_VOICE=1

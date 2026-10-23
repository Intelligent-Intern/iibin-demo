GPU ?= auto
ifeq ($(GPU),auto)
GPU_AVAILABLE := $(shell nvidia-smi -L >/dev/null 2>&1 && docker info --format '{{if index .Runtimes "nvidia"}}yes{{end}}' 2>/dev/null)
else ifeq ($(GPU),1)
GPU_AVAILABLE := yes
else ifeq ($(GPU),0)
GPU_AVAILABLE :=
else
$(error GPU must be auto, 1 or 0)
endif
COMPOSE := docker compose -f compose.yaml $(if $(filter yes,$(GPU_AVAILABLE)),-f compose.gpu.yaml)

.PHONY: build up down logs
build:
	$(MAKE) -C ../iibin-js build
	$(MAKE) -C ../iibin-py build
	$(COMPOSE) build
up:
	$(COMPOSE) up -d
	@echo 'Werkraum: http://localhost:5206 — Qwen: $(if $(filter yes,$(GPU_AVAILABLE)),NVIDIA GPU,CPU)'
down:
	$(COMPOSE) down
logs:
	$(COMPOSE) logs -f --tail=100

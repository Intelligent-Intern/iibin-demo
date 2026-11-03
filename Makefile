VOICE ?= 0
export VOICE
export BUILD_TARGET := $(if $(filter 1,$(VOICE)),voice,runtime)
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
COMPOSE := docker compose -f compose.yaml $(if $(and $(filter 1,$(VOICE)),$(filter yes,$(GPU_AVAILABLE))),-f compose.gpu.yaml) $(if $(filter 1,$(VOICE)),--profile voice)

.PHONY: build up down logs test
build:
	$(MAKE) -C ../iibin-js build
	$(MAKE) -C ../iibin-py build
	$(COMPOSE) build
up:
	$(COMPOSE) up -d
	@echo 'Lunar Charge Control: http://localhost:5206'
down:
	$(COMPOSE) down
logs:
	$(COMPOSE) logs -f --tail=100

test:
	node --test tests/lunar-engine.test.mjs tests/presentation.test.mjs
	python3 -m unittest discover -s tests -p 'test_*.py'

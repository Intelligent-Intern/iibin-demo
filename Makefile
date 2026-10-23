.PHONY: build up down logs
build:
	$(MAKE) -C ../iibin-js build
	$(MAKE) -C ../iibin-py build
	docker compose build
up:
	docker compose up -d
	@echo 'Werkraum: http://localhost:5206'
down:
	docker compose down
logs:
	docker compose logs -f --tail=100

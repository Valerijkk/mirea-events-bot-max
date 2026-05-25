# =============================================================================
# mirea-events-bot — короткие команды для повседневной работы.
# =============================================================================
# Каждая цель — независима. Запускайте:  make <цель>
# =============================================================================

.PHONY: help install bootstrap run dev test clean reset docker-build docker-up docker-down docker-logs docker-db

help:
	@echo "Доступные команды:"
	@echo "  make install       — поставить зависимости"
	@echo "  make bootstrap     — БД + admin + ИПТИП + парсинг событий МИРЭА"
	@echo "  make run           — запустить приложение (prod-режим)"
	@echo "  make dev           — запустить приложение с auto-reload"
	@echo "  make test          — прогнать unit-тесты"
	@echo "  make clean         — удалить локальную БД, QR и ics"
	@echo "  make reset         — clean + bootstrap (БД с нуля)"
	@echo "  make docker-build  — собрать Docker-образы (compose build)"
	@echo "  make docker-up     — поднять через docker compose"
	@echo "  make docker-down   — остановить docker compose"
	@echo "  make docker-logs   — логи всех сервисов compose"
	@echo "  make docker-db     — psql в контейнер postgres"

install:
	cd backend && pip install -r requirements.txt

bootstrap:
	cd backend && python -m app.cli.init_project

run:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080

dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

test:
	cd testing-framework && pytest -m unit -v

clean:
	rm -rf data/mirea-events.db data/qr data/ics

reset: clean bootstrap
	@echo "База сброшена и заполнена с нуля."

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-db:
	docker compose exec db psql -U mirea -d mirea_events

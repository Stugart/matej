SHELL := /bin/bash
.DEFAULT_GOAL := help

API_DIR := apps/api
WORKER_DIR := apps/worker

.PHONY: help dev up down logs ps api worker migrate revision test lint format clean

help:
	@echo "Kutaj AI Core — Make targets"
	@echo ""
	@echo "  make dev                spustí postgres + redis (docker compose)"
	@echo "  make down               zastaví služby"
	@echo "  make logs               tail logov služieb"
	@echo "  make ps                 stav služieb"
	@echo ""
	@echo "  make api                spustí FastAPI dev server (port 8000)"
	@echo "  make worker             spustí arq background worker"
	@echo ""
	@echo "  make migrate            aplikuje DB migrácie (alembic upgrade head)"
	@echo "  make revision m='msg'   vytvorí novú Alembic migráciu"
	@echo ""
	@echo "  make test               pytest"
	@echo "  make lint               ruff check ."
	@echo "  make format             ruff format ."
	@echo ""
	@echo "  make clean              zmaže __pycache__, .pytest_cache, .ruff_cache"

dev:
	docker compose up -d

up: dev

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

api:
	cd $(API_DIR) && uvicorn kutaj_api.main:app --reload --host 127.0.0.1 --port 8000

worker:
	cd $(WORKER_DIR) && arq kutaj_worker.main.WorkerSettings

migrate:
	cd $(API_DIR) && alembic upgrade head

revision:
	@if [ -z "$(m)" ]; then echo "Použitie: make revision m='popis migracie'"; exit 1; fi
	cd $(API_DIR) && alembic revision --autogenerate -m "$(m)"

test:
	cd $(API_DIR) && pytest -q

lint:
	ruff check .

format:
	ruff format .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +

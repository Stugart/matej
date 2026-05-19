# Kutaj AI Core

Osobný „druhý mozog" pre Mateja — nahrávanie hlasových poznámok, automatický prepis,
AI analýza, projektová pamäť a sémantické vyhľadávanie.

Hlavná doména: `speech.kutaj.com`.

## Stack

- Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic 2, Alembic
- PostgreSQL 16 + `pgvector` + `pg_trgm` + `citext`
- Redis + `arq` (async background worker)
- OpenAI Whisper API (speech-to-text)
- Anthropic Claude (analýza, sumarizácia, extrakcia úloh)
- Nginx (TLS terminácia, reverse proxy, X-Accel-Redirect pre audio)
- Debian 12 / Ubuntu 24.04 LTS

Architektonický princíp: **WordPress nikdy nie je na kritickej ceste spracovania.**
WP smie byť tenká UI vrstva, mozog beží mimo neho.

## Repo layout

```
apps/api      FastAPI HTTP API + Alembic migrácie
apps/worker   arq background worker (transcribe -> clean -> analyze -> embed)
infra/        nginx vhost, systemd unit files, backup skripty
docs/         DEPLOYMENT, BACKUP, ROLLBACK runbooky
```

## Quick start (lokálny dev)

Prerekvizity: Docker + Docker Compose, Python 3.12, `make`.

```bash
cp .env.example .env
# uprav .env: doplň APP_SECRET_KEY, JWT_SECRET_KEY (openssl rand -hex 32)
# doplň OPENAI_API_KEY, ANTHROPIC_API_KEY z password manageru

make dev          # postgres + redis cez docker compose
make migrate      # aplikuje DB migrácie
make api          # FastAPI dev server: http://127.0.0.1:8000
# v druhom termináli:
make worker       # arq background worker
```

Health: `curl http://127.0.0.1:8000/api/v1/health`

## Dokumentácia

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — produkčný deploy na Debian server
- [docs/BACKUP.md](docs/BACKUP.md) — záloha DB, audia, restore drill
- [docs/ROLLBACK.md](docs/ROLLBACK.md) — postupy keď deploy zlyhá

## Status

`P0` — repo skeleton. Žiadne aplikačné endpointy okrem `/health`, `/ready`.
Plán a roadmapa v komentároch k tasku, neskôr presunúť do `docs/ARCHITECTURE.md`.

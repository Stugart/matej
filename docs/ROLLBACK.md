# Rollback runbook

> **Princíp:** každá zmena má rollback. Ak nemá, neideme do produkcie.
> Pri pochybnostiach — **rolluj**. Druhý pokus o deploy je lacnejší než hodina downtime.

## Kedy rollovať

Kritériá (ak platí aspoň jedno, rolluj):

- `GET /api/v1/ready` zlyháva > 5 min po deploymente
- worker padá v slučke (`journalctl -u kutaj-worker -f` ukazuje opakované crashes)
- DB migrácia spadla v polovici (Alembic ukáže "current" verziu inú než cieľ)
- 5xx pomer > 5% za posledných 10 min v `journalctl -u kutaj-api`
- audio upload (smoke test) zlyháva

## 1. Rollback aplikácie (kód)

```bash
# Aktuálny tag
sudo -u kutaj git -C /opt/kutaj/app describe --tags

# Vrátiť na predošlý tag
sudo -u kutaj git -C /opt/kutaj/app fetch --tags
sudo -u kutaj git -C /opt/kutaj/app checkout <previous-tag>

# Preinštalovať (kvôli zmeneným balíkom v pyproject.toml)
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/api
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/worker

# Reštart
sudo systemctl restart kutaj-api kutaj-worker

# Check
curl -sS https://speech.kutaj.com/api/v1/health
sudo journalctl -u kutaj-api -n 30 --no-pager
```

## 2. Rollback DB migrácie

**Najprv skontroluj**, či má migrácia funkčný `downgrade()`. Netriviálne migrácie
(drop column, data backfill) často nemajú — vtedy ide len `pg_restore`.

### Variant A — Alembic downgrade
```bash
cd /opt/kutaj/app/apps/api
sudo -u kutaj env $(grep -v '^#' /etc/kutaj/.env | xargs) \
    /opt/kutaj/.venv/bin/alembic downgrade -1

# Check
sudo -u kutaj env $(grep -v '^#' /etc/kutaj/.env | xargs) \
    /opt/kutaj/.venv/bin/alembic current
```

### Variant B — pg_restore z pre-migrate dumpu

**Pozor:** všetky dáta zapísané po dumpe sú stratené. Skontroluj `audit_log`,
prípadne ručne vyexportuj nové riadky pred restore.

```bash
# 1. Stop application — zabrániť ďalším zápisom
sudo systemctl stop kutaj-api kutaj-worker

# 2. Záloha aktuálneho stavu (pre prípad, že restore zlyhá)
sudo -u postgres pg_dump -Fc kutaj > /var/kutaj/backups/before_restore_$(date +%F-%H%M).dump

# 3. Restore
sudo -u postgres pg_restore --clean --if-exists -d kutaj \
    /var/kutaj/backups/pre_migrate_<TIMESTAMP>.dump

# 4. Štart
sudo systemctl start kutaj-api kutaj-worker

# 5. Smoke test
curl -sS https://speech.kutaj.com/api/v1/ready
```

## 3. Rollback systemd unit

Pred každou zmenou unit-u:
```bash
sudo cp /etc/systemd/system/kutaj-api.service \
        /etc/systemd/system/kutaj-api.service.bak.$(date +%F-%H%M)
```

Rollback:
```bash
sudo cp /etc/systemd/system/kutaj-api.service.bak.<TIMESTAMP> \
        /etc/systemd/system/kutaj-api.service
sudo systemctl daemon-reload
sudo systemctl restart kutaj-api
```

## 4. Rollback nginx config

```bash
# Predpoklad: pred deployom si urobil
#   sudo cp -a /etc/nginx /etc/nginx.bak.<date>

sudo rsync -a --delete /etc/nginx.bak.<date>/ /etc/nginx/
sudo nginx -t
sudo systemctl reload nginx

# Check
curl -I https://speech.kutaj.com
```

## 5. Plný rollback (nuclear option)

Ak je deploy úplne rozbitý a treba vrátiť celý stav servera:

```bash
# 1. Zastaviť všetko
sudo systemctl stop kutaj-api kutaj-worker nginx

# 2. Obnoviť DB
sudo -u postgres pg_restore --clean --if-exists -d kutaj \
    /var/kutaj/backups/pre_deploy_<TIMESTAMP>.dump

# 3. Vrátiť kód
sudo -u kutaj git -C /opt/kutaj/app fetch --tags
sudo -u kutaj git -C /opt/kutaj/app checkout <last-known-good-tag>
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/api
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/worker

# 4. Vrátiť nginx
sudo rsync -a --delete /etc/nginx.bak.<date>/ /etc/nginx/

# 5. Spustiť
sudo systemctl start nginx kutaj-api kutaj-worker

# 6. Overiť
curl -sS https://speech.kutaj.com/api/v1/ready
sudo journalctl -u kutaj-api -u kutaj-worker -n 100 --no-pager
```

## 6. Po rollbacku — postmortem

Po každom rollbacku napíš stručný záznam (5-10 riadkov):

- čo sa stalo,
- prečo to neodhalil test alebo smoke test,
- aké signály sme prehliadli,
- čo zmeníme v procese, aby sa to neopakovalo.

Ulož do `docs/incidents/YYYY-MM-DD-<short-name>.md`.
Priečinok `docs/incidents/` vytvoríme až keď bude prvý incident.

## 7. Rýchla diagnostika pred rozhodnutím o rollbacku

```bash
# Stav služieb
sudo systemctl --failed
sudo systemctl status kutaj-api kutaj-worker nginx postgresql redis-server

# Posledné chyby
sudo journalctl -u kutaj-api -p err -n 50 --no-pager
sudo journalctl -u kutaj-worker -p err -n 50 --no-pager

# DB connection
sudo -u postgres psql -d kutaj -c "SELECT now(), version();"

# Redis
redis-cli ping
redis-cli llen arq:queue:default     # počet čakajúcich jobov

# Disk
df -h /var /var/kutaj /srv
du -sh /var/kutaj/audio /var/kutaj/backups

# Pamäť
free -h
```

Ak vidíš jasnú príčinu (napr. plný disk, OOM-killer zastrelil worker),
oprav ju **najprv** — nemusí byť potrebný rollback kódu.

# Deployment — Debian 12 / Ubuntu 24.04

Produkčný deploy Kutaj AI Core na čistý server. Cieľová doména: `speech.kutaj.com`.

> **Pravidlo:** každý krok má **Backup → Príkaz → Check → Rollback**.
> Ak Check nesedí, **nepokračuj**, urob Rollback a diagnostikuj.

## 0. Predpoklady

- Server: Debian 12 alebo Ubuntu 24.04 LTS, min. 4 GB RAM, 50+ GB disk.
- Root / sudo prístup.
- DNS `speech.kutaj.com` smeruje na IP servera (A record).
- Otvorené porty zvonku: 80, 443. Port 22 ideálne cez VPN / IP whitelist.
- Žiadny iný service na portoch 80/443.

## 1. Príprava systému

### 1.1 Aktualizácia balíkov

**Backup:** `dpkg --get-selections > ~/dpkg.before.$(date +%F).txt`

**Príkaz:**
```bash
sudo apt update
sudo apt upgrade -y
```

**Check:** `apt list --upgradable 2>/dev/null | tail -n +2` musí byť prázdne.

**Rollback:** selektívne `apt install <package>=<old-version>` podľa `dpkg.before.*.txt`.

### 1.2 Service user

**Backup:** `getent passwd kutaj && echo "user už existuje, preskoč krok"`

**Príkaz:**
```bash
sudo useradd --system --create-home --home-dir /opt/kutaj --shell /usr/sbin/nologin kutaj
```

**Check:** `id kutaj` vráti uid/gid.

**Rollback:** `sudo userdel -r kutaj`

### 1.3 Adresáre

**Príkaz:**
```bash
sudo install -d -o kutaj -g kutaj -m 0750 /var/kutaj /var/kutaj/audio /var/kutaj/tmp /var/kutaj/backups
sudo install -d -o kutaj -g kutaj -m 0750 /var/log/kutaj
sudo install -d -o root  -g root  -m 0755 /etc/kutaj
```

**Check:**
```bash
ls -la /var/kutaj /var/log/kutaj /etc/kutaj
# /var/kutaj* musí byť kutaj:kutaj 0750
# /etc/kutaj musí byť root:root 0755
```

**Rollback:** `sudo rm -rf /var/kutaj /var/log/kutaj /etc/kutaj`

## 2. PostgreSQL 16 + pgvector

### 2.1 Inštalácia

**Príkaz (Debian 12):**
```bash
sudo apt install -y postgresql-16 postgresql-16-pgvector
```

Pre Ubuntu 24.04 použij oficiálny PGDG repo, ak `postgresql-16-pgvector` nie je v base.

**Check:** `sudo systemctl is-active postgresql` → `active`

**Rollback:** `sudo apt purge -y postgresql-16 postgresql-16-pgvector && sudo apt autoremove -y`

### 2.2 DB + user + extensions

**Backup:**
```bash
sudo -u postgres pg_dumpall > ~/pg_before_kutaj.$(date +%F).sql
```

**Príkaz:**
```bash
sudo -u postgres createuser --no-superuser --no-createrole --no-createdb kutaj
sudo -u postgres createdb -O kutaj kutaj
sudo -u postgres psql -d kutaj -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d kutaj -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
sudo -u postgres psql -d kutaj -c "CREATE EXTENSION IF NOT EXISTS citext;"

# Náhodné heslo, ulož do password manageru:
PGPASS=$(openssl rand -hex 24)
sudo -u postgres psql -c "ALTER USER kutaj WITH ENCRYPTED PASSWORD '$PGPASS';"
echo "DB heslo (zapíš do password manageru a do .env): $PGPASS"
```

**Check:**
```bash
sudo -u postgres psql -d kutaj -c "\dx" | grep -E 'vector|pg_trgm|citext'   # 3 riadky
```

**Rollback:**
```bash
sudo -u postgres dropdb kutaj
sudo -u postgres dropuser kutaj
```

## 3. Redis

**Príkaz:**
```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
```

**Check:** `redis-cli ping` → `PONG`

**Rollback:** `sudo apt purge -y redis-server`

## 4. Aplikácia

### 4.1 Python 3.12 + ffmpeg

**Príkaz:**
```bash
sudo apt install -y python3.12 python3.12-venv python3-pip ffmpeg
```

**Check:** `python3.12 --version` → `Python 3.12.x`

### 4.2 Klon repa

**Príkaz:**
```bash
sudo -u kutaj git clone https://github.com/stugart/matej.git /opt/kutaj/app
cd /opt/kutaj/app
sudo -u kutaj git checkout <prod-tag>      # napr. v0.1.0 — NIE main
```

**Check:** `sudo -u kutaj git -C /opt/kutaj/app describe --tags`

**Rollback:** `sudo rm -rf /opt/kutaj/app`

### 4.3 Virtualenv + závislosti

**Príkaz:**
```bash
sudo -u kutaj python3.12 -m venv /opt/kutaj/.venv
sudo -u kutaj /opt/kutaj/.venv/bin/pip install --upgrade pip
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/api
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/worker
```

**Check:**
```bash
sudo -u kutaj /opt/kutaj/.venv/bin/python -c "import kutaj_api, kutaj_worker; print('ok')"
```

**Rollback:** `sudo rm -rf /opt/kutaj/.venv`

### 4.4 .env

**Backup:**
```bash
[ -f /etc/kutaj/.env ] && sudo cp /etc/kutaj/.env /etc/kutaj/.env.bak.$(date +%F-%H%M)
```

**Príkaz:**
```bash
sudo cp /opt/kutaj/app/.env.example /etc/kutaj/.env
sudo nano /etc/kutaj/.env       # doplň heslá a API kľúče
sudo chown root:kutaj /etc/kutaj/.env
sudo chmod 0640 /etc/kutaj/.env
```

**Check:**
```bash
sudo -u kutaj cat /etc/kutaj/.env > /dev/null && echo "kutaj môže čítať .env"
ls -la /etc/kutaj/.env       # musí byť -rw-r----- root:kutaj
```

**Rollback:** `sudo mv /etc/kutaj/.env.bak.<TIMESTAMP> /etc/kutaj/.env`

### 4.5 DB migrácie

**Backup (povinné pred každou migráciou):**
```bash
sudo -u postgres pg_dump -Fc kutaj > /var/kutaj/backups/pre_migrate_$(date +%F-%H%M).dump
```

**Príkaz:**
```bash
cd /opt/kutaj/app/apps/api
sudo -u kutaj env $(grep -v '^#' /etc/kutaj/.env | xargs) \
    /opt/kutaj/.venv/bin/alembic upgrade head
```

**Check:**
```bash
sudo -u kutaj env $(grep -v '^#' /etc/kutaj/.env | xargs) \
    /opt/kutaj/.venv/bin/alembic current
```

**Rollback:** viď [ROLLBACK.md § Rollback DB migrácie](ROLLBACK.md).

## 5. Systemd

### 5.1 kutaj-api.service

**Príkaz:**
```bash
sudo cp /opt/kutaj/app/infra/systemd/kutaj-api.service.example /etc/systemd/system/kutaj-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now kutaj-api.service
```

**Check:**
```bash
sudo systemctl status kutaj-api.service
curl -sS http://127.0.0.1:8000/api/v1/health     # {"status":"ok"}
```

**Rollback:**
```bash
sudo systemctl disable --now kutaj-api.service
sudo rm /etc/systemd/system/kutaj-api.service
sudo systemctl daemon-reload
```

### 5.2 kutaj-worker.service

Analogicky ako 5.1 — `kutaj-worker.service.example` → `kutaj-worker.service`.

**Check (worker po štarte zaloguje pripojenie k Redisu):**
```bash
sudo journalctl -u kutaj-worker -n 30 --no-pager | grep -i "ready"
```

## 6. Nginx + TLS

### 6.1 Inštalácia

**Príkaz:**
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 6.2 Site config

**Backup:**
```bash
sudo cp -a /etc/nginx /etc/nginx.bak.$(date +%F)
```

**Príkaz:**
```bash
sudo cp /opt/kutaj/app/infra/nginx/kutaj.conf.example /etc/nginx/sites-available/speech.kutaj.com
sudo ln -sf /etc/nginx/sites-available/speech.kutaj.com /etc/nginx/sites-enabled/speech.kutaj.com
sudo nginx -t
sudo systemctl reload nginx
```

**Check:** `curl -I http://speech.kutaj.com` → 301 na HTTPS (po Certbote) alebo 200.

**Rollback:**
```bash
sudo rm /etc/nginx/sites-enabled/speech.kutaj.com
sudo nginx -t && sudo systemctl reload nginx
```

### 6.3 TLS (Let's Encrypt)

**Príkaz:**
```bash
sudo certbot --nginx -d speech.kutaj.com --redirect --agree-tos -m admin@kutaj.com
```

**Check:** `curl -I https://speech.kutaj.com` → 200 + `strict-transport-security` header.

**Rollback:** `sudo certbot delete --cert-name speech.kutaj.com`

## 7. Smoke test (po deployi)

```bash
# 1. Health & readiness
curl -sS https://speech.kutaj.com/api/v1/health
curl -sS https://speech.kutaj.com/api/v1/ready    # všetky komponenty "ok"

# 2. Logy
sudo journalctl -u kutaj-api -n 50 --no-pager
sudo journalctl -u kutaj-worker -n 50 --no-pager

# 3. Test workera — enqueue ping job (až keď bude implementovaný v K4)
# kutaj-cli worker:ping

# 4. Audio storage nie je verejne dostupné
curl -I https://speech.kutaj.com/audio/   # MUSÍ 404 alebo 403, NIKDY 200 listing
```

## 8. Štruktúra súborov na serveri

```
/opt/kutaj/app/             git checkout, read-only pre kutaj usera
/opt/kutaj/.venv/           virtualenv
/etc/kutaj/.env             secrets, 0640 root:kutaj
/var/kutaj/audio/           audio súbory, 0750 kutaj:kutaj
/var/kutaj/tmp/             upload tmp
/var/kutaj/backups/         lokálne pg_dump-y
/var/log/kutaj/             logy (nepovinné, primárne použijeme journald)
/etc/systemd/system/kutaj-api.service
/etc/systemd/system/kutaj-worker.service
/etc/nginx/sites-available/speech.kutaj.com
```

## 9. Aktualizácie (následné deploye)

```bash
# 1. Backup DB
sudo -u postgres pg_dump -Fc kutaj > /var/kutaj/backups/pre_deploy_$(date +%F-%H%M).dump

# 2. Pull + checkout nového tagu
sudo -u kutaj git -C /opt/kutaj/app fetch --tags
sudo -u kutaj git -C /opt/kutaj/app checkout <new-tag>

# 3. Závislosti
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/api
sudo -u kutaj /opt/kutaj/.venv/bin/pip install -e /opt/kutaj/app/apps/worker

# 4. Migrácie (zachytí padnutie)
cd /opt/kutaj/app/apps/api
sudo -u kutaj env $(grep -v '^#' /etc/kutaj/.env | xargs) \
    /opt/kutaj/.venv/bin/alembic upgrade head

# 5. Reštart
sudo systemctl restart kutaj-api kutaj-worker

# 6. Smoke test (§ 7)
```

Ak ktorýkoľvek krok zlyhá → ROLLBACK.md.

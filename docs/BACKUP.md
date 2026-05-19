# Backup stratégia

> **Pravidlo:** záloha, ktorú si nikdy neobnovil, neexistuje.
> Restore drill je **povinný raz za 3 mesiace**.

## Čo zálohujeme

| Komponent | Frekvencia | Retencia (lokálne) | Off-site |
|---|---|---|---|
| PostgreSQL (kutaj DB) | denne 02:30 | 14 denných + 8 týždenných + 6 mesačných | áno (týždenne) |
| Audio (`/var/kutaj/audio`) | denne 03:00 | 30 dní lokálne | áno (týždenne, navždy) |
| `/etc/kutaj/.env` | pri zmene | password manager | n/a |
| Nginx, systemd configs | pri zmene | git (`infra/`) + `/etc/nginx.bak.<date>` | n/a |
| Audit log (DB) | súčasť pg_dump | min. 1 rok | áno |

Aplikačné logy sa **nezálohujú** mimo journalctl rotácie — sú diagnostické,
nie zdroj pravdy. Zdroj pravdy je `audit_log` tabuľka v DB.

## 1. PostgreSQL — denný dump

### Cron

`/etc/cron.d/kutaj-pg-backup`:
```
30 2 * * *  postgres  /opt/kutaj/app/infra/scripts/backup_pg.sh >> /var/log/kutaj/backup.log 2>&1
```

### Skript

`infra/scripts/backup_pg.sh` (bude vytvorený v K5):
```bash
#!/usr/bin/env bash
set -euo pipefail
DEST=/var/kutaj/backups
TS=$(date +%F)
pg_dump -Fc -d kutaj > "$DEST/kutaj_$TS.dump.tmp"
mv "$DEST/kutaj_$TS.dump.tmp" "$DEST/kutaj_$TS.dump"

# Retencia: posledných 14 denných
ls -1t "$DEST"/kutaj_*.dump | tail -n +15 | xargs -r rm --
```

### Check
```bash
ls -lh /var/kutaj/backups/ | head
file /var/kutaj/backups/kutaj_*.dump | tail -1   # "PostgreSQL custom database dump"
# najnovší dump musí byť z dnešnej noci:
find /var/kutaj/backups -name 'kutaj_*.dump' -mtime -1
```

## 2. Audio — incremental rsync

### Cron

`/etc/cron.d/kutaj-audio-backup`:
```
0 3 * * *  root  /opt/kutaj/app/infra/scripts/backup_audio.sh >> /var/log/kutaj/backup.log 2>&1
```

### Skript

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC=/var/kutaj/audio/
DEST=/srv/backup/audio                       # iný disk / mountpoint, NIE /var/kutaj
TODAY=$(date +%F)
mkdir -p "$DEST"
rsync -a --delete --link-dest="$DEST/latest" "$SRC" "$DEST/$TODAY/"
ln -sfn "$DEST/$TODAY" "$DEST/latest"

# Retencia: 30 dní
find "$DEST" -maxdepth 1 -type d -name '????-??-??' -mtime +30 -exec rm -rf {} +
```

Hardlink-based rotácia → každý deň vyzerá ako plný snapshot, ale zaberá
miesto len pre zmenené súbory.

### Check
```bash
ls /srv/backup/audio/ | tail
du -sh /srv/backup/audio/$(date +%F)
```

## 3. Off-site — týždenne (restic)

Cieľ: druhý fyzický stroj alebo cloud storage (Hetzner Storage Box, Wasabi, S3).

```bash
# /etc/cron.d/kutaj-offsite
15 4 * * 0  root  /opt/kutaj/app/infra/scripts/backup_offsite.sh >> /var/log/kutaj/backup.log 2>&1
```

```bash
#!/usr/bin/env bash
set -euo pipefail
# RESTIC_REPOSITORY a RESTIC_PASSWORD sú v /etc/kutaj/backup.env (0600 root:root)
source /etc/kutaj/backup.env
restic backup /var/kutaj/audio /var/kutaj/backups
restic forget --keep-weekly 8 --keep-monthly 12 --prune
restic check --read-data-subset=5%       # 5% reálnych dát skontrolujeme
```

`/etc/kutaj/backup.env` (vlastník root:root, 0600):
```
export RESTIC_REPOSITORY=sftp:offsite-host:/kutaj
export RESTIC_PASSWORD=<silne-heslo-z-pwd-managera>
```

## 4. `.env` a tajomstvá

- **Nie v repo.** `.gitignore` to chráni, ale ostražitosť.
- **Nie v zálohe servera** ako plaintext (vrátane snapshotov VM-iek).
- Šifrovaná kópia v password manageri (1Password / Bitwarden / Vaultwarden).
- Pri každej zmene → aktualizovať password manager **predtým**, než reštartuješ
  service. Inak hrozí, že stratíš heslo a nevieš sa vrátiť.

## 5. Restore drill (povinný raz za 3 mesiace)

```bash
# 1. Nová DB na staging
sudo -u postgres dropdb --if-exists kutaj_restore
sudo -u postgres createdb kutaj_restore
sudo -u postgres pg_restore -d kutaj_restore /var/kutaj/backups/kutaj_<latest>.dump

# 2. Sanity check (až keď budú existovať tabuľky):
sudo -u postgres psql -d kutaj_restore -c "SELECT count(*) FROM notes;"
sudo -u postgres psql -d kutaj_restore -c "SELECT max(created_at) FROM notes;"

# 3. Audio z off-site
mkdir -p /tmp/restore_test
restic restore latest --target /tmp/restore_test
ls /tmp/restore_test/var/kutaj/audio/ | head

# 4. Zapíš výsledok do incident logu:
#    /opt/kutaj/app/docs/incidents/YYYY-MM-DD-restore-drill.md
#    - dátum
#    - aký dump
#    - počet záznamov
#    - rezíduum stratenej hodiny (RPO)
#    - poznámky
```

**Ak drill zlyhá**, považuj backup za nefunkčný a oprav ho **predtým**, než
budeš pokračovať v inom development.

## 6. Rýchla referencia (cheat sheet)

```bash
# Manuálny backup pred ručným zásahom:
sudo -u postgres pg_dump -Fc kutaj > /var/kutaj/backups/manual_$(date +%F-%H%M)_$USER.dump

# Stav záloh:
ls -lh /var/kutaj/backups/ | head
du -sh /srv/backup/audio/latest

# Veľkosti zaberá DB:
sudo -u postgres psql -d kutaj -c "SELECT pg_size_pretty(pg_database_size('kutaj'));"
```

# Running and deploying GraphMaster

Two halves: **running it on your own machine**, and **putting it on a server**.
The first needs nothing but Docker. The second needs Docker, a domain and about
forty minutes.

---

## Part 1 · Run it locally

### 1.1 Get the code

The work is merged into `main`, so:

```bash
git checkout main
git pull origin main
```

If you have local changes you do not want, stash them first (`git stash`).

### 1.2 The easy path — Docker

You need [Docker Desktop](https://docs.docker.com/get-started/get-docker/)
running. Nothing else: no Python, no Node, no PostgreSQL.

```bash
# 1. Create the one required secret.
#    macOS/Linux:
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
#    Windows PowerShell:
#    "SECRET_KEY=$(-join ((1..64) | ForEach-Object {'{0:x}' -f (Get-Random -Max 16)}))" | Out-File -Encoding ascii .env

# 2. Build and start everything.
docker compose up --build

# 3. Wait. The first build takes 5–10 minutes: it downloads the spaCy model,
#    the NLTK data and the OCR weights. Later starts take seconds.
```

When the log says `Application startup complete`, open:

| | |
|---|---|
| **The app** | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health | http://localhost:8000/api/v1/health/ready |

The database is migrated and seeded automatically on first start — vocabulary
categories, terms, avatars and achievement rules are all there.

**Stop it:** `Ctrl-C`, then `docker compose down`.
**Careful:** `docker compose down -v` also deletes the database volume.

### 1.3 Create your first account

Register at http://localhost:3000/register. New accounts are students.

To make yourself a **teacher** or **administrator**, promote the account once
from the database:

```bash
docker compose exec db psql -U graphmaster -d graphmaster \
  -c "UPDATE users SET role='admin' WHERE email='you@example.com';"
```

Sign out and back in — the role is in your token. From then on you can manage
everyone else from the Users screen.

### 1.4 The development path — hot reload

Use this when you are changing code and want the page to refresh as you save.
It needs **Python 3.12**, **Node 22** and **PostgreSQL 16** installed.

```bash
# Terminal 1 — database only, from Docker
docker compose up db

# Terminal 2 — backend
cp backend/.env.example backend/.env      # then edit SECRET_KEY
make install                              # virtualenv + dependencies + spaCy model
make migrate
make seed
make dev                                  # http://localhost:8000

# Terminal 3 — frontend
cp frontend/.env.example frontend/.env.local
make web-install
make web-dev                              # http://localhost:3000
```

Useful while working:

```bash
make check      # everything CI runs, both halves
make test       # backend suite with coverage
make web-check  # prettier, eslint, build, typecheck, tests
make reset-db   # drop, recreate, migrate and seed
```

### 1.5 If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `SECRET_KEY must be set` | No `.env` at the repo root | §1.2 step 1 |
| Every request fails with a CORS error | `ALLOWED_ORIGINS` does not match the URL in your browser | It must be the **browser's** origin, exactly — `http://localhost:3000`, not `127.0.0.1` |
| The app loads but nothing fetches | `NEXT_PUBLIC_API_URL` was wrong **when the image was built** | It is baked in at build time. Change it and rebuild: `docker compose build web` |
| `port is already allocated` | Something else is on 3000/8000/5432 | Set `WEB_PORT`, `API_PORT` or `DB_PORT` in `.env` |
| First build seems stuck | It is downloading the language models | Give it ten minutes once |

---

## Part 2 · Deploy to a server

Any host that runs Docker: a £5/month VPS (Hetzner, DigitalOcean, Linode), a
university VM, or AWS Lightsail. **2 GB RAM minimum, 4 GB comfortable** — spaCy
and the OCR models are the memory, and the production overlay runs two API
workers.

### 2.1 Prepare the server

```bash
ssh you@your-server
curl -fsSL https://get.docker.com | sh          # Docker + compose plugin
sudo usermod -aG docker $USER                    # then log out and back in

git clone https://github.com/rayhandevcs-tech/graphmaster-ai.git
cd graphmaster-ai
```

### 2.2 Write the production environment

**This is the step that matters.** The base compose file is a development
stack — it defaults `DEBUG` to true and the database password to
`graphmaster`. `docker-compose.prod.yml` overrides those and makes the
dangerous ones *required*, so a missing variable stops the stack instead of
silently choosing something unsafe.

Create `.env` next to `docker-compose.yml`:

```bash
cat > .env <<EOF
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
ALLOWED_ORIGINS=https://graphmaster.example.edu
NEXT_PUBLIC_API_URL=https://graphmaster.example.edu/api/v1
EOF

chmod 600 .env
```

Replace `graphmaster.example.edu` with your real domain, twice. Both URLs are
what the **browser** will use, not what the server calls itself.

> `.env` is git-ignored and must stay that way. It is the only copy of your
> database password.

### 2.3 Start it

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Both files, every time — the second one is an *overlay*, not a replacement.
Make it a habit or put it in a shell alias, because starting with only the base
file silently reverts you to development defaults.

Check it came up:

```bash
docker compose ps                    # api should read (healthy) within ~2 min
docker compose logs -f api
curl -s localhost:8000/api/v1/health/ready
```

### 2.4 Put HTTPS in front

The stack listens on 3000 and 8000 over plain HTTP. Do not expose those. Put
Caddy in front — it gets certificates automatically:

```bash
sudo apt install -y caddy
sudo tee /etc/caddy/Caddyfile <<'EOF'
graphmaster.example.edu {
    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle {
        reverse_proxy localhost:3000
    }
}
EOF
sudo systemctl reload caddy
```

Then close everything else:

```bash
sudo ufw allow 22,80,443/tcp
sudo ufw enable
```

Postgres is **not** published by the production overlay, so it is unreachable
from outside the host by design. To attach a client, use
`docker compose exec db psql -U graphmaster -d graphmaster`.

### 2.5 Back up the database — do this before anyone uses it

There is no automatic backup. Three things live only in these volumes and
nothing can recompute them: the XP ledger (`xp_events` is append-only), every
submission and score, and the handwriting uploads.

```bash
mkdir -p ~/backups
cat > ~/backup-graphmaster.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd ~/graphmaster-ai
STAMP=$(date +%F-%H%M)
docker compose exec -T db pg_dump -U graphmaster graphmaster | gzip > ~/backups/db-$STAMP.sql.gz
docker run --rm -v graphmaster-ai_uploads_data:/data -v ~/backups:/out \
  alpine tar czf /out/uploads-$STAMP.tar.gz -C /data .
find ~/backups -name '*.gz' -mtime +30 -delete
EOF
chmod +x ~/backup-graphmaster.sh

# Nightly at 03:00
(crontab -l 2>/dev/null; echo "0 3 * * * ~/backup-graphmaster.sh") | crontab -
```

**Then rehearse the restore once, before you need it:**

```bash
gunzip -c ~/backups/db-2026-08-27-0300.sql.gz | \
  docker compose exec -T db psql -U graphmaster -d graphmaster
```

A backup you have never restored is a hypothesis, not a backup. Copy the
`~/backups` directory somewhere off the machine as well — a snapshot on the
same disk does not survive the disk.

### 2.6 Updating

```bash
cd ~/graphmaster-ai
~/backup-graphmaster.sh                          # always first
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Migrations run automatically on start and are forward-only.

### 2.7 Optional extras

**Grammar analysis** is off by default — it is a JVM with a few hundred
megabytes of dictionaries. To enable it:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile grammar up -d
# then set GRAMMAR_PROVIDER=local in .env and restart the api
```

Nothing about a score, an XP award or a leaderboard changes either way — it
adds diagnostic findings a teacher reads.

**Error tracking.** There is none. Logs are structured JSON with a request id
on every line, but nothing aggregates or alerts on them, so a 500 in production
is discovered when somebody tells you. A free Sentry project and one
`sentry-sdk` initialisation would close that.

---

## What is deliberately not automated

| | Why |
|---|---|
| Backups | Where they go is a decision about your institution's storage, not the app's |
| TLS certificates | Caddy does it in four lines; baking a reverse proxy into compose would fight whatever the host already runs |
| Horizontal scaling | Rate limiting and scoring are both in-process today, so a second replica needs shared state first. See the production readiness review. |
| Session and rate-limiter cleanup | Both functions exist; neither is scheduled yet |

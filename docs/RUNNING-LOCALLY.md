# Running GraphMaster locally

Everything you need to get the whole stack up on your own machine. Nothing
here is about deployment — for that see
[DEPLOYMENT.md](DEPLOYMENT.md), which puts the frontend on Vercel and the
backend on Render.

The `docker-compose.yml` this page uses is the **development** stack, and it
is deliberately not the thing that runs in production.

---

## 1. Get the code

The work is merged into `main`, so:

```bash
git checkout main
git pull origin main
```

If you have local changes you do not want, stash them first (`git stash`).

## 2. The easy path — Docker

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

## 3. Create your first account

Register at http://localhost:3000/register. New accounts are students.

To make yourself a **teacher** or **administrator**, promote the account once
from the database:

```bash
docker compose exec db psql -U graphmaster -d graphmaster \
  -c "UPDATE users SET role='admin' WHERE email='you@example.com';"
```

Sign out and back in — the role is in your token. From then on you can manage
everyone else from the Users screen.

## 4. The development path — hot reload

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

## 5. If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `SECRET_KEY must be set` | No `.env` at the repo root | §1.2 step 1 |
| Every request fails with a CORS error | `ALLOWED_ORIGINS` does not match the URL in your browser | It must be the **browser's** origin, exactly — `http://localhost:3000`, not `127.0.0.1` |
| The app loads but nothing fetches | `NEXT_PUBLIC_API_URL` was wrong **when the image was built** | It is baked in at build time. Change it and rebuild: `docker compose build web` |
| `port is already allocated` | Something else is on 3000/8000/5432 | Set `WEB_PORT`, `API_PORT` or `DB_PORT` in `.env` |
| First build seems stuck | It is downloading the language models | Give it ten minutes once |

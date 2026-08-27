# Deployment — Frontend on Vercel, Backend on Render

This guide deploys GraphMaster as two pieces:

| Piece | Where | What |
|---|---|---|
| Frontend (`frontend/`) | **Vercel** | Next.js 15, built per deploy |
| Backend (`backend/`) + PostgreSQL | **Render** | FastAPI in Docker + managed Postgres |

> The repo's `docker-compose.yml` is a **development** stack. It is not used in
> this deployment. See `docs/proposals/production-readiness-review.md` for the
> gaps it has as a production target.

---

## 0. Before you start

- A GitHub repo Render and Vercel can both read.
- A Render account and a Vercel account.
- **Decide the cookie strategy now — read §3 first.** The refresh-token cookie
  is `SameSite=Lax`. `*.vercel.app` and `*.onrender.com` are *different sites*,
  so a browser will refuse to store that cookie from a cross-site response and
  **login breaks after 30 minutes / on every reload**. §3 has three fixes; the
  clean one needs a domain you control.

Cost floor: Render `standard` web ($25/mo) + `basic-256mb` Postgres ($6/mo).
The API image loads spaCy + PyTorch + EasyOCR and OOMs on anything smaller.
§6 has a lighter build that fits `starter` if cost matters.

---

## 1. Backend + database on Render

### 1a. Create the stack from the blueprint

`render.yaml` at the repo root describes both the database and the API.

1. Render dashboard → **New → Blueprint** → select this repo.
2. Render shows `graphmaster-db` and `graphmaster-api`. Apply.
3. The first API deploy **will fail or crash-loop** — `DATABASE_URL` and
   `ALLOWED_ORIGINS` are not set yet. That is expected; finish the next steps.

### 1b. Set `DATABASE_URL`

1. Open **graphmaster-db** → copy the **Internal Database URL**. It looks like
   `postgresql://graphmaster:xxxx@dpg-xxxx-a/graphmaster`.
2. Change the scheme to `postgresql+asyncpg://` — the async engine reads the
   driver from the URL. Alembic and the entrypoint strip it back off themselves.
   ```
   postgresql+asyncpg://graphmaster:xxxx@dpg-xxxx-a/graphmaster
   ```
3. **graphmaster-api → Environment** → set `DATABASE_URL` to that value.

### 1c. Set `ALLOWED_ORIGINS`

Leave it for now — you need the Vercel URL first. Come back after §2.

### 1d. What the container does on boot

`backend/scripts/entrypoint.sh` runs automatically on every start:

1. waits for the database,
2. `alembic upgrade head` — creates / migrates all tables,
3. `python -m app.db.seed.cli` — seeds avatars, vocabulary, badges, achievements
   (idempotent; sample graphs are skipped until a teacher/admin exists — see §4),
4. starts uvicorn.

No manual migrate step. Watch **Logs** for `Application startup complete`.

### 1e. Health

Render pings `/api/v1/health/live`. Once green, check:
`https://graphmaster-api.onrender.com/api/v1/health/ready` → should report
`database: ok`, `nlp: ok`, and OCR providers.

---

## 2. Frontend on Vercel

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory: `frontend`**. Framework preset: Next.js (auto).
3. Build & output settings: leave defaults (`next build`). `frontend/types/api.ts`
   is committed, so the build does not need a running API.
4. **Environment Variables** (Production + Preview):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://graphmaster-api.onrender.com/api/v1` |

   `NEXT_PUBLIC_*` is inlined into the browser bundle **at build time**. Vercel
   rebuilds on every deploy with this set, so it is baked correctly — this is
   the one place the Docker "build arg" footgun does not bite you. Change it →
   redeploy.
5. Deploy. Note the resulting URL, e.g. `https://graphmaster.vercel.app`.
6. Back on **Render → graphmaster-api → Environment**, set
   `ALLOWED_ORIGINS` = `https://graphmaster.vercel.app` (exact, no trailing
   slash). Save — the API redeploys.

At this point the app loads and you can register, **but read §3** or logins
will silently stop working within half an hour.

---

## 3. The cross-site cookie problem (must fix one of these)

`POST /auth/login` and `/auth/refresh` set an **HttpOnly refresh cookie**. The
code sets it `SameSite=Lax; Secure` ([`backend/app/api/v1/auth.py`](../backend/app/api/v1/auth.py)).
`Lax` means the browser only sends — and only *stores* — that cookie for
**same-site** requests. `graphmaster.vercel.app` → `graphmaster-api.onrender.com`
is cross-site, so:

- the cookie from the login response is **dropped by the browser**,
- `AuthProvider`'s bootstrap refresh on page load always fails,
- the access token in memory dies after `ACCESS_TOKEN_EXPIRE_MINUTES` (30) with
  no way to renew → the user is logged out and cannot get back in without
  re-entering their password.

Pick one:

### Option A — custom sub-domains (recommended, no code change)

Put both halves on **one registrable domain**:

| Host | Points to |
|---|---|
| `graphmaster.example.com` | Vercel (add as a domain on the Vercel project) |
| `api.example.com` | Render (add as a custom domain on graphmaster-api) |

`graphmaster.example.com` and `api.example.com` are the **same site**, so the
`Lax` cookie is stored and sent. Then:

- Vercel env: `NEXT_PUBLIC_API_URL = https://api.example.com/api/v1`
- Render env: `ALLOWED_ORIGINS = https://graphmaster.example.com`

Both platforms issue the TLS certificates automatically. This is the least
fragile setup and keeps large file uploads going straight to Render.

### Option B — proxy the API through the frontend (no code change, no domain)

Make the browser talk **only** to the Vercel origin; Vercel forwards `/api/*`
to Render server-side, so the cookie is first-party for `*.vercel.app`.

Add to [`frontend/next.config.ts`](../frontend/next.config.ts):

```ts
async rewrites() {
  return [
    {
      source: "/api/:path*",
      destination: `${process.env.BACKEND_ORIGIN}/api/:path*`,
    },
  ];
},
```

Vercel env vars:

| Name | Value |
|---|---|
| `BACKEND_ORIGIN` | `https://graphmaster-api.onrender.com` (server-side, **not** `NEXT_PUBLIC_`) |
| `NEXT_PUBLIC_API_URL` | `/api/v1` (relative — the browser now calls its own origin) |

Render env: `ALLOWED_ORIGINS = https://graphmaster.vercel.app` (kept as a
belt-and-braces; CORS is not hit through the proxy).

**Trade-off:** every API call double-hops through Vercel, and Vercel's proxy has
a request-body size limit (~4.5 MB on Hobby). Handwriting photos can exceed
that and fail to upload. Fine for a typed-submission demo, not for heavy OCR
testing. Prefer Option A if you can.

### Option C — make the cookie cross-site capable (small code change)

Change the cookie to `SameSite=None; Secure` in production. In
`backend/app/api/v1/auth.py`, `_set_refresh_cookie`:

```python
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
```

`SameSite=None` **requires** `Secure`, which is already true in production. The
frontend already sends `credentials: "include"` on every request, and the API
already sets `allow_credentials=True` with an explicit origin allowlist, so no
other change is needed. Update the CI cookie test if it asserts `lax`.

This keeps uploads going straight to Render and needs no domain, at the cost of
a one-line divergence from the repo.

---

## 4. First admin and the sample graph library

Public registration only creates **students**. The seeded practice library
needs a teacher/admin as its author, so:

1. Register yourself in the app (you become a student).
2. Promote that account. Render → **graphmaster-db → Connect → PSQL command**,
   or use `psql` locally against the External URL:
   ```sql
   UPDATE users SET role='admin' WHERE email='you@example.com';
   ```
3. Re-run the seed. Render → **graphmaster-api → Shell**:
   ```bash
   python -m app.db.seed.cli
   ```
   It logs `Sample graphs: 4 created`.
4. Log out and back in (the old token still says `student`).

Assign further teachers from the app: as admin, **/admin/users** → edit a user →
Role → Teacher.

---

## 5. Backups (do this before real data exists)

`postgres_data` on Render is the dissertation's dataset and the only copy of
`xp_events`. There is no recompute path.

- Render `basic` Postgres and up include **daily automated backups** with
  point-in-time recovery — confirm it is on under the database's **Recovery** tab.
- Also take your own periodic dump you control:
  ```bash
  pg_dump "<External Database URL>" -Fc -f graphmaster-$(date +%F).dump
  ```
- Rehearse the restore once:
  ```bash
  pg_restore --clean --if-exists -d "<target URL>" graphmaster-YYYY-MM-DD.dump
  ```
- Never run `docker compose down -v` against anything holding real data.

---

## 6. Optional: a lighter backend image (fits Render `starter`, ~$7/mo)

The default image bakes EasyOCR + PyTorch (~7 GB, ~1 GB RAM at rest). Dropping
them leaves Tesseract as the only OCR provider (already apt-installed, tiny) and
keeps typed submissions and all scoring fully working — spaCy stays.

In `backend/Dockerfile`:

- builder stage: `pip install ".[reports]"` instead of `".[ocr,reports]"`
- delete the `RUN ... easyocr.Reader(...)` line and the `COPY --from=builder
  /opt/easyocr ...` line
- runtime stage: drop `libgl1` (only EasyOCR's OpenCV needed it); keep
  `tesseract-ocr`

Set `OCR_PROVIDER_ORDER=tesseract` on Render. Handwriting OCR quality drops;
nothing else changes. Revert by restoring the four lines.

---

## 7. Redeploying after code changes

| Changed | Do |
|---|---|
| Frontend code | push to the tracked branch → Vercel auto-builds |
| Backend code | push → Render auto-builds (`autoDeploy: true`) and re-runs migrations on boot |
| A new migration | nothing extra — the entrypoint applies it on the next deploy |
| `NEXT_PUBLIC_API_URL` | change in Vercel → **redeploy** (it is compiled in) |
| Env var on Render | save → the service restarts itself |

---

## 8. Quick checklist

- [ ] `render.yaml` blueprint applied; `graphmaster-db` + `graphmaster-api` exist
- [ ] `DATABASE_URL` set with the `postgresql+asyncpg://` scheme
- [ ] API `/api/v1/health/ready` is green
- [ ] Vercel project, Root Directory `frontend`, `NEXT_PUBLIC_API_URL` set
- [ ] `ALLOWED_ORIGINS` on Render = the exact frontend URL
- [ ] One of §3 A / B / C done and login survives a page reload
- [ ] First admin promoted, `seed.cli` re-run, 4 sample graphs visible
- [ ] Database backups confirmed on, one manual `pg_dump` taken and restore tried

# Deployment — Frontend on Vercel, Backend on Render

This guide deploys GraphMaster as three pieces:

| Piece | Where | What |
|---|---|---|
| Frontend (`frontend/`) | **Vercel** | Next.js 15, built per deploy |
| Backend (`backend/`) | **Render** | FastAPI in Docker |
| PostgreSQL | **Neon** | Managed, and free permanently — see §0 |

> The repo's `docker-compose.yml` is a **development** stack. It is not used in
> this deployment. See `docs/proposals/production-readiness-review.md` for the
> gaps it has as a production target.

---

## 0. Before you start

- A GitHub repo Render and Vercel can both read, with the code on the branch
  those services will build (**`main`**, unless you point them elsewhere).
- Accounts on **Render**, **Vercel** and **Neon**.

### Which plan this guide assumes

It walks the **free** path, because that is the one with the sharp edges. The
paid deltas are in §6 and they are all simplifications.

| | Free (this guide) | Paid |
|---|---|---|
| Frontend | Vercel Hobby | same |
| API | Render **free** web service | Render `standard`, $25/mo |
| Database | **Neon** free | Render Postgres `basic-256mb`, $6/mo |
| OCR | Tesseract only (`INCLUDE_EASYOCR=0`) | + EasyOCR |
| Uploads survive a deploy | **No** — no disk on free | Yes, 1 GB disk |
| API sleeps when idle | **Yes**, ~50s to wake | No |

Three consequences of "free" that are not settings, and are better known now
than discovered later:

- **The API sleeps after 15 minutes** and takes about a minute to answer the
  next request. Before a demo, open the site once and leave it.
- **There is no disk**, so the *stored photograph* of a handwritten answer is
  gone after any restart. The recognised text, the score, the XP and every
  figure are in Postgres and survive.
- **There is no Shell** on a free Render service. §4 does the one job that
  needed it another way.

> Why Neon rather than Render's own free Postgres: Render deletes a free
> database after 30 days. Neon's free tier is permanent. `xp_events` is
> append-only and has no recompute path (CLAUDE.md rule 9) — losing it loses
> the dissertation's dataset.

---

## 1. Database on Neon, API on Render

### 1a. Create the database

1. [console.neon.tech](https://console.neon.tech) → **New Project**. Name it
   `graphmaster`; pick the region nearest you (Singapore for Bangladesh).
2. **Connection string** → copy the **pooled** one. It looks like
   `postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require`.
3. Change the scheme to `postgresql+asyncpg://` — the async engine reads its
   driver from the URL. Alembic and the entrypoint strip it back off
   themselves.
4. **Delete `?sslmode=require` from the end.** `asyncpg` does not accept that
   parameter and fails to connect with it present; it negotiates TLS with Neon
   regardless. This is the single most common way this step goes wrong.

   Keep the finished string to hand:
   ```
   postgresql+asyncpg://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb
   ```

### 1b. Create the API from the blueprint

`render.yaml` at the repo root describes the web service. It no longer
describes a database — that is Neon's job now.

1. Render dashboard → **New → Blueprint** → select this repo.
2. Render shows `graphmaster-api`. Apply.
3. The first build takes 10–20 minutes: it installs spaCy and bakes its
   language model into the image.
4. That first deploy **will crash-loop**. `DATABASE_URL` and `ALLOWED_ORIGINS`
   are not set yet. Expected — carry on.

### 1c. Set `DATABASE_URL`

**graphmaster-api → Environment** → set `DATABASE_URL` to the string from §1a.
Save. The service redeploys and should now reach `Application startup
complete` in the logs.

`ALLOWED_ORIGINS` needs the Vercel URL, so leave it until §2.

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
2. **Root Directory: `frontend`**. Framework preset: Next.js (auto-detected).
3. Build settings: leave the defaults. `frontend/types/api.ts` is committed, so
   the build never needs a running API.
4. **Environment Variables** (Production *and* Preview):

   | Name | Value | Why |
   |---|---|---|
   | `NEXT_PUBLIC_API_URL` | `/api/v1` | Relative. The browser calls its own origin — see §3. |
   | `BACKEND_ORIGIN` | `https://graphmaster-api.onrender.com` | Server-side only. Next rewrites `/api/*` here. |

   `BACKEND_ORIGIN` has **no** `NEXT_PUBLIC_` prefix on purpose: it is read in
   `next.config.ts` at request time, never shipped to the browser.

   `NEXT_PUBLIC_*` *is* inlined into the browser bundle **at build time**, so
   changing it means redeploying, not restarting.
5. Deploy. Note the URL, e.g. `https://graphmaster.vercel.app`.
6. Back on **Render → graphmaster-api → Environment**, set
   `ALLOWED_ORIGINS` = `https://graphmaster.vercel.app` — exact, no trailing
   slash. Save; the API redeploys.

The app now loads and you can register. The two variables in step 4 are what
keep you logged in — §3 explains why.

---

## 3. The cross-site cookie problem (this setup uses Option B)

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

### Option B — proxy the API through the frontend (**already in the code**)

Make the browser talk **only** to the Vercel origin; Vercel forwards `/api/*`
to Render server-side, so the cookie is first-party for `*.vercel.app`.

The rewrite is already in
[`frontend/next.config.ts`](../frontend/next.config.ts) and switches itself on
when `BACKEND_ORIGIN` is set — so §2 step 4 is the whole of this option. There
is nothing to edit.

Render still wants `ALLOWED_ORIGINS` set as belt-and-braces; CORS is not
actually reached through the proxy.

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

Public registration only ever creates **students**. The seeded practice
library needs a teacher or admin to own it, so it is skipped until one exists.

1. **Register yourself in the app.** You are a student.
2. **Promote the account.** Neon console → your project → **SQL Editor**:
   ```sql
   UPDATE users SET role = 'admin' WHERE email = 'you@example.com';
   ```
   It should report `UPDATE 1`. If it reports `UPDATE 0`, the email does not
   match — check for a typo or a different case.
3. **Re-run the seed.** The entrypoint runs it on *every* boot and it is
   idempotent, so all this needs is a restart: Render →
   **graphmaster-api → Manual Deploy → Deploy latest commit**.

   > The paid path would use **Shell → `python -m app.db.seed.cli`**. Free
   > services have no shell, which is why this is a redeploy instead.

   Watch the logs for `Sample graphs: 4 created`.
4. **Log out and back in.** Your existing token still says `student`; nothing
   re-reads the role until you get a new one.

Further teachers are promoted from inside the app: as admin, **/admin/users**
→ edit a user → Role → Teacher.

---

## 5. Backups (do this before there is real data)

The database holds the only copy of `xp_events`, which is append-only and has
no recompute path (CLAUDE.md rule 9). Losing it loses the evaluation dataset.

- Neon's free tier keeps a short window of point-in-time history — useful for
  "I just ran the wrong `UPDATE`", not for "this project is finished and I
  need the data in six months".
- So take your own dump you control, from the **direct** (non-pooled)
  connection string:
  ```bash
  pg_dump "postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require" \
    -Fc -f graphmaster-$(date +%F).dump
  ```
  Note the scheme here is plain `postgresql://` and `sslmode=require` stays —
  `pg_dump` is not `asyncpg` and wants both.
- **Rehearse the restore once**, into a scratch Neon branch:
  ```bash
  pg_restore --clean --if-exists -d "<scratch URL>" graphmaster-YYYY-MM-DD.dump
  ```
  An untested backup is a hope, not a backup.
- Before every viva or milestone, take one and keep it off the laptop.

---

## 6. Going paid

Everything below is an upgrade, not a fix. Each is independent.

### 6a. EasyOCR back in

The free path sets `INCLUDE_EASYOCR=0`, which builds the image without
EasyOCR and PyTorch — roughly 7 GB of image and a gigabyte of resident memory
that a 512 MB instance does not have. Tesseract is left as the only
recognition provider: handwriting still works, and reads less well. Typed
submissions and every part of scoring are identical either way.

To restore the full provider chain you need the memory first:

1. **graphmaster-api → Settings → Instance Type → `standard`** (2 GB, $25/mo).
2. **Environment** → `INCLUDE_EASYOCR` = `1`, and delete
   `OCR_PROVIDER_ORDER` so the default chain applies.
3. Manual Deploy. The build is much longer — it bakes the recognition models
   into the image rather than fetching them per request.

Render passes a service's environment variables to the Docker build as build
arguments, which is why one variable is enough to change what gets installed.

### 6b. A disk, so uploads survive

Free instances cannot mount disks, so the stored photograph of a handwritten
answer is lost on every restart. `render.yaml` carries the disk definition
commented out; uncomment it and re-sync the blueprint:

```yaml
disk:
  name: uploads
  mountPath: /app/storage
  sizeGB: 1
```

A disk pins the service to a single instance. That is already true here.

### 6c. No sleeping

Any paid instance type stays warm. This is the single change that most
improves how the app feels — the free tier's ~50 second wake is the first
thing anyone notices.

### 6d. Render's own Postgres

If you would rather not keep the database at Neon, `render.yaml` also carries
the managed database commented out, on `basic-256mb` ($6/mo) because the free
tier is deleted after 30 days. Use the **Internal** Database URL, with the
same `postgresql+asyncpg://` scheme change as §1a — and no `?sslmode=` on it
either.

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

Ordered. Each line is a thing that breaks the next one if it is skipped.

- [ ] Code is on the branch Render and Vercel build (`main` by default)
- [ ] Neon project created; pooled URL rewritten to `postgresql+asyncpg://`
      **with `?sslmode=require` removed**
- [ ] Render blueprint applied; `DATABASE_URL` set; logs reach
      `Application startup complete`
- [ ] `/api/v1/health/ready` reports `database: ok` and `nlp: ok`
- [ ] Vercel project imported with **Root Directory `frontend`**
- [ ] Vercel has `NEXT_PUBLIC_API_URL=/api/v1` **and** `BACKEND_ORIGIN=<render url>`
- [ ] Render has `ALLOWED_ORIGINS=<vercel url>`, exact, no trailing slash
- [ ] Registered, promoted to `admin` in Neon's SQL editor, redeployed the API,
      logged out and back in
- [ ] `Sample graphs: 4 created` in the API logs
- [ ] One full run through: pick a graph → type an answer → submit → a tier
      animation plays and XP is awarded
- [ ] A `pg_dump` taken, and a restore rehearsed once

### When it does not work

| What you see | Almost always |
|---|---|
| API crash-loops, logs mention `sslmode` | `?sslmode=require` left on `DATABASE_URL` |
| API crash-loops, logs mention OOM / killed | `INCLUDE_EASYOCR` is not `0` on a free instance |
| First request takes ~50s | The free instance was asleep. Not a fault. |
| Login works, then logs out on reload | `BACKEND_ORIGIN` missing, or `NEXT_PUBLIC_API_URL` is absolute |
| Practice library is empty | No admin existed when the seed last ran — redo §4 |
| A submitted handwriting image 404s later | No disk on free (§6b). The text and score are fine. |
| CORS error in the browser console | `ALLOWED_ORIGINS` has a trailing slash or the wrong host |

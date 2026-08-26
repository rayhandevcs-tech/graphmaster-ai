# Production & Dissertation Readiness Review

**Reviewed at:** `34cab5e`. No code changed.
**Method:** repository read end to end — 22 tables, 4 migrations, 7 CI jobs, the
compose stack, both Dockerfiles, the entrypoint, the rate limiter, the auth
path, the assessment framework, and the frontend at three widths. Figures below
are measured, not estimated.

---

## 0. Where the project actually stands

| | |
|---|---|
| Tests | **1,858** — 1,580 backend, 278 frontend |
| Coverage | 99% backend (target 80%, NFR-5.2) |
| Schema | 22 tables · 31 foreign keys · 48 CHECK constraints · 15 UNIQUE · 70 indexes |
| Migrations | 4, forward-only, round-tripped from empty in CI |
| CI | 7 jobs: lint · secret scan · backend tests with an 80% floor · migrations · frontend build+tests · generated-type drift · compose |
| Containers | Multi-stage, non-root (uid 1000/1001), frontend `output: standalone` with a HEALTHCHECK |
| External services | None required |

**The software is finished. The deployment is not.** Every critical finding
below is about running it, not about building it — which is a good position to
be in six weeks before a defence, and a bad one to discover in the last week.

---

## A. Critical issues

### A1 · Following the README to deploy ships a debug build with a default database password

`docker-compose.yml` is a development stack wearing production clothes:

```
ENVIRONMENT: ${ENVIRONMENT:-development}
DEBUG:       ${DEBUG:-true}
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-graphmaster}
ports: ["${DB_PORT:-5432}:5432"]        # Postgres published to the host
```

`SECRET_KEY` is correctly required (`:?`). Nothing else is. A deployer who sets
only `SECRET_KEY` — which is what the compose file's own error message tells
them to do — gets `DEBUG=true`, a database whose password is its username, and
that database reachable from the internet on 5432.

**Fix:** a `docker-compose.prod.yml` overlay that requires `POSTGRES_PASSWORD`
with `:?`, forces `ENVIRONMENT=production` and `DEBUG=false`, and either drops
the `db` port mapping or binds it to `127.0.0.1`. Add `POSTGRES_PASSWORD` to
`.env.example`, which does not currently mention it.

### A2 · There is no backup, and the data is irreplaceable

`postgres_data` and `uploads_data` are named volumes with no dump, no schedule,
no retention and no documented restore. Three things live only there:

- **`xp_events`** — append-only by design, and the sole record of every award.
  There is no path that recomputes it from anything else.
- **`submissions` and `scores`** — the dissertation's dataset.
- **Handwriting uploads** — the evidence behind every OCR claim.

A volume lost to a misconfigured `docker compose down -v` takes the evaluation
chapter with it. This is the single highest-consequence gap in the project.

**Fix:** `pg_dump` on a schedule to storage outside the host, a documented
restore rehearsed once, and a retention policy. It is an afternoon.

---

## B. High-priority issues

### B1 · Scoring blocks the event loop, and one worker serves everything

`grep` for `to_thread`, `run_in_executor` across `app/services`, `app/nlp` and
`app/assessment` returns **nothing**. The spaCy parse, seven analyzers and the
optional grammar HTTP call all run synchronously inside the async handler.
`tests/perf` budgets **2 seconds** for a 300-word analysis (NFR-1.2), and
neither compose nor the Dockerfile passes `--workers`.

So: while one submission is scored, the process serves nothing else — not
another student, not `/health/ready`. Effective concurrent scoring throughput is
about **0.5 requests per second**, and the failure mode is head-of-line blocking
on every endpoint.

The scenario this meets is a class of thirty pressing *Submit* in the last five
minutes of a lesson.

PROJECT_PLAN §1.4 decision 11 records this as accepted, with the reasoning that
the budget is bounded. That reasoning holds for *one* request and does not
address contention. **Recommend `asyncio.to_thread` around `analyse()` plus
`--workers 2` before any real cohort uses it.** Both are small; the first wants
its own load test, which is exactly what decision 11 says.

### B2 · The API container has no healthcheck

`db` and `languagetool` have one. `api` does not, despite `/health/ready`
existing and being tested. Nothing restarts a wedged worker, and `web`'s
`depends_on: api` is a start-order hint rather than a readiness gate.

### B3 · Two unbounded growth paths, both known and neither scheduled

| What grows | Why | Where |
|---|---|---|
| Rate-limiter buckets | `RateLimiter.prune()` is defined and **never called** | `app/core/rate_limit.py:86` |
| `auth_sessions` rows | `delete_expired()` is defined and **never called** | `app/repositories/auth_session.py:39` |

The first is an in-process dict keyed by client IP — on a public deployment it
grows with distinct addresses and never shrinks. The second is recorded as
decision 4 "left as an operational task for Sprint 14"; Sprint 14 has not done
it.

### B4 · Migrations run from the entrypoint on every start

`scripts/entrypoint.sh` runs `alembic upgrade head` then seeds. Convenient for
one container and a race for two: Alembic takes no lock, so two replicas
starting together can both attempt the same revision.

**Fix:** a one-shot migrate job, or a Postgres advisory lock around the upgrade.
Not urgent at one replica — but it is the thing that breaks the *first* time
someone scales out, which is the worst moment to find it.

### B5 · No error tracking

Structured JSON logging via `pythonjsonlogger` is in place and good, with a
request id on every line. Nothing aggregates it, nothing alerts. A 500 in
production is discovered when a student tells a teacher who emails you.

For a dissertation deployment a hosted Sentry free tier is twenty minutes and
turns "it broke last Tuesday" into a stack trace with a request id.

---

## C. Medium-priority issues

| # | Issue | Note |
|---|---|---|
| C1 | **The practice library shows no graphs** | Audit F7. `GraphSummary` carries no `chart_data`, so a library about charts is a list of labels. Needs an API-contract decision, not a component change. |
| C2 | **Writing consistency is unreachable** | Endpoint implemented, tested, teacher-gated; no screen calls it. Feature shipped and invisible. |
| C3 | **No deployment or API documentation** | README has *Development* and no *Deployment*. Sprint 14's stated guides do not exist. OpenAPI is served but no reference is published. |
| C4 | **Rate limiting is per-process** | Documented and deliberate; the effective limit multiplies by replica count, which matters the moment B1's `--workers 2` lands. |
| C5 | **Settings is one 2,705px column** | Audit F9. The fix is a section rail, not two columns. |
| C6 | **The task prompt sits below the fold** | Audit F12. A student can start writing without seeing the instruction. |
| C7 | **3 high advisories in the frontend** | `sharp` via `next`. Pre-existing; the fix is a major Next upgrade and wants its own change. |
| C8 | **`uploads_data` has no retention** | Superseded handwriting images are kept deliberately (decision 4) and never expire. |

---

## D. Nice to have

- Automated contrast measurement in CI (the palette was designed to AA and is
  test-enforced against literals, but never measured).
- A screen-reader transcript pass with a real reader.
- A screen-by-screen review at 768px — measured for overflow, never inspected.
- Drop NLTK: declared in `pyproject.toml`, unused since Sprint 5, costs a corpus
  download in every image build (decision 2).
- `GraphSummary` thumbnails (resolves C1).

---

## Reviews by dimension

### Architecture — strong
Clean layering enforced by convention and reviewed in CI (routers → services →
repositories, domain exceptions never `HTTPException`). The assessment
framework's analyzer protocol, supervisor failure isolation, audience filtering
and version fingerprinting are genuinely good engineering: an analyzer that
throws degrades the assessment to `partial` rather than failing the score, and
`assessment_version` fingerprints the rubric rather than the code. **No
duplicate systems found.** The one architectural risk is B1, and it is
documented rather than hidden.

### Security — good, with deployment gaps
Bcrypt with an explicit overlong-input rejection; HS256; 30-minute access and
30-day rotating refresh tokens in a server-side session table; security headers
(`nosniff`, `DENY`, HSTS); CORS from an allowlist; rate limits on auth, password
reset, upload and analyze; magic-byte upload validation with an explicit
decompression-bomb guard that replaces Pillow's; a secret-scanning CI job; and
audience filtering that cannot be widened by environment.

Gaps are A1 (defaults), B3 (unbounded buckets) and the absence of dependency
scanning in CI. No injection surface found — everything goes through SQLAlchemy
constructs.

### UX — strong
Every student surface routes to practice; no dead ends. Absence is rendered as
absence everywhere (`—`, never `0`), which is the rule most products get wrong.
The reward layer ends in recovery by construction rather than by convention.
Remaining: C1, C5, C6.

### Accessibility — strong
Measured after Sprint 14: **zero interactive targets below 44px** across eleven
screens at 390px, one documented WCAG 2.5.8 exemption, **exactly one `<h1>` per
page**, zero horizontal overflow. Data-table alternatives on every chart; polite
announcements on filter changes; podium DOM order 1-2-3; reduced motion renders
settled frames. Not yet done: automated contrast, real screen-reader testing.

### Mobile — strong
Dense tables reflow to cards below `md` on the queue, vocabulary manager and
user list. Bottom navigation fits five teacher destinations. Filters collapse on
the library. Nothing scrolls sideways at any width.

### Performance — good single-user, unproven concurrent
NFR-1.1 (500ms reads) and NFR-1.2 (2s analysis) are asserted by `tests/perf`,
deselected by default and run via `make perf`. Frontend first-load is 102 kB
shared, 107–191 kB per route, with Chart.js and framer-motion both lazily
loaded. **No concurrent load test exists**, which is precisely where B1 lives.

### Scalability — single-instance by design
Honest and documented: in-process rate limiting, in-process scoring, entrypoint
migrations, `analytics_snapshots` deliberately unused so every analytic is
computed live. All correct for the target deployment; all become wrong together
the moment a second replica starts. The seams are marked in code, which is the
right preparation.

### Database — strong
48 CHECK constraints and 15 UNIQUEs is unusually rigorous. The subtle ones are
right: `NULLS NOT DISTINCT`/partial indexes where a plain UNIQUE over nullable
columns would constrain nothing; `clock_timestamp()` on `xp_events` so four
awards in one transaction order correctly; `users.total_xp` recomputed from the
ledger rather than incremented. Migrations are hand-reviewed after autogenerate
because autogenerate misses exactly these.

### API — strong
81 operations, 65 paths, consistent pagination and error envelope, generated
frontend types with a CI drift check. 403-not-empty on a class you do not teach;
503-not-500 for a missing optional library; audience filtering by assembly
rather than by blanking. Missing: a published reference (C3), and versioning
beyond the `/v1` prefix is unaddressed — acceptable for a single-tenant
deployment.

---

## Dissertation review

### Strengths

**The rejection is the contribution.** A documented design review that evaluates
nine integrity signals and rejects three — authorship attribution, behavioural
telemetry, cross-student overlap — on stated technical and ethical grounds is a
stronger ethics chapter than an implemented detector. Most projects in this
space ship the classifier and defend it afterwards.

**The reflexivity finding is publishable.** That the platform's own feedback
names the vocabulary a student then uses — so the system causes the change it
later measures — is a real methodological result about instrumented learning
platforms, and this system is instrumented to demonstrate it.

**Constraints enforced in code, not policy.** `NEVER_STUDENT_ANALYZERS` as a
frozen set no environment can raise, and a consistency layer with no write path
to scores, XP or leaderboards, are the kind of evidence an examiner can verify
in ten seconds.

**Provable requirements.** FR-7.7 ("the hammer always recovers") is asserted
against an array rather than a stopwatch. That technique generalises and is
worth a paragraph.

### Threats to validity — and the two that are serious

| Threat | Severity | Note |
|---|---|---|
| **No real cohort data** | **Critical** | Everything demonstrated is seeded. There is a systems chapter and no evaluation chapter. |
| **Writing consistency is at stage 1 of 3** | **Critical** | Promotion to stage 3 is gated on one teaching term of dark collection. The longitudinal chapter cannot begin until stage 2 starts. |
| No ground truth for any integrity claim | Accepted | Which is why the detector was rejected; state this explicitly rather than letting an examiner raise it. |
| Single institution, single language pair | High | Limits generalisation; declare it. |
| The platform teaches what it measures | High | The reflexivity finding — present it as a result, not a caveat. |
| Scoring heuristics unvalidated against human markers | High | 70/30 weighting and the writing sub-scores have no inter-rater study. A small one (2 markers, 30 scripts, Cohen's κ) would answer the obvious question. |
| Assessment coverage is partial by construction | Medium | Submissions marked before the engine existed carry none; every figure reports `assessed_count`, which is honest and needs saying. |

### The two actions that most improve the dissertation

1. **Start stage-2 collection now.** It is blocked on one written decision (the
   subject-access answer), not on code, and its cost is measured in months. Every
   week of delay is a week off the longitudinal dataset.
2. **Run a small inter-rater study.** Two human markers, thirty scripts, against
   the engine. It converts "the scoring is a heuristic" from a limitation into a
   measured agreement figure, and it is the first thing a viva will probe.

---

## GraphMaster Release Readiness Score

### **78 / 100**

| Dimension | Weight | Score | Weighted | Why |
|---|---|---|---|---|
| Functional completeness | 15 | 100 | 15.0 | Every specified function reachable, tested, green in CI |
| Code quality & tests | 15 | 95 | 14.3 | 1,858 tests, 99% coverage, 7 CI jobs, clean layering |
| Architecture | 10 | 90 | 9.0 | Strong; B1 is a known, documented limit |
| Database | 10 | 95 | 9.5 | 48 checks, correct partial indexes, forward-only migrations |
| API design | 10 | 90 | 9.0 | Consistent, typed, drift-checked; no published reference |
| Security | 10 | 75 | 7.5 | Application strong; deployment defaults unsafe (A1) |
| Accessibility | 8 | 92 | 7.4 | Measured: 0 sub-44px, 1 h1/page, 0 overflow |
| UX & mobile | 7 | 88 | 6.2 | Three medium items remain |
| **Deployment readiness** | **10** | **35** | **3.5** | No prod overlay, no guide, no API healthcheck |
| **Operations** | **5** | **20** | **1.0** | **No backups, no error tracking, no cleanup jobs** |
| Scalability | 5 | 60 | 3.0 | Single-instance by design and honest about it |
| | **105→100** | | **78.4** | |

### Why it is not higher

Two of the three lowest scores are the same sentence: **nobody has run this in
production, and the artefacts that only matter in production do not exist.**
There is no backup, no alerting, no production compose profile, and no hosting
guide. A2 alone would cap the score — a system whose data cannot be restored is
not production-ready however good the code is.

### Why it is not lower

Everything that is hard is done, and done unusually well. The 22-table schema
with 48 CHECK constraints, 1,858 tests at 99% coverage, seven CI jobs including
migration round-tripping and generated-type drift, non-root multi-stage images,
and an assessment framework with staged audiences and failure isolation are
above the standard this class of project is judged at. The remaining work is a
day of DevOps and an afternoon of documentation, not a sprint of engineering.

### What moves it to 90+

| Action | Effort | Gain |
|---|---|---|
| A1 · production compose overlay | 2h | +4 |
| A2 · `pg_dump` schedule + rehearsed restore | 3h | +5 |
| B2 · API healthcheck | 15m | +1 |
| B5 · Sentry free tier | 30m | +2 |
| B3 · two cleanup jobs | 2h | +1 |
| C3 · deployment guide + API reference | 4h | +2 |

**≈ 12 hours to 93/100.** None of it is engineering risk; all of it is the work
that turns a finished system into a deployable one.

# GraphMaster — Project Plan

**Version:** 1.2
**Status:** In progress — backend sprints 1–8 delivered, frontend not started
**Branch:** `claude/graphmaster-platform-9aba5t`

---

## 1. Delivery status

**Last updated:** end of Sprint 8 (analytics and exports).

### 1.1 Snapshot

| Item | State |
|---|---|
| Backend sprints complete | **8 of 9** (Sprints 1–8) |
| Frontend sprints complete | **0 of 5** (Sprints 10–14) |
| API endpoints | 75 operations across 59 paths |
| Application modules | 120 Python files |
| Tests | **871 passing**, 44 test modules |
| Coverage | **95%** (target 80%, NFR-5.2) |
| Migrations | 3, forward-only, applied cleanly |
| Lint / format | `ruff` and `black` clean |

At the start of this plan the repository held nothing but documentation. The
gap analysis in §2 below describes that starting point and the conflicts
resolved before any code was written; it is kept as the record of *why* the
schema looks the way it does.

### 1.2 What is built

| Sprint | Delivered | Notes |
|---|---|---|
| **0** | This plan, the SRS, all 9 architecture docs realigned to the specification | — |
| **1** | FastAPI skeleton, layered architecture, typed settings, full SQLAlchemy 2.0 schema, Alembic, seed data, Dockerfile, compose, health checks | — |
| **2** | JWT access + rotating refresh tokens, bcrypt hashing, RBAC dependencies, registration with gender→avatar assignment, profile endpoints, rate limiting | Refresh-token families revoked on replay |
| **3** | Vocabulary CRUD (7 categories, 25+ seeded terms), graph CRUD with Chart.js data, per-graph target curation, class management | Publishing requires ≥1 required target |
| **4** | Storage abstraction, magic-byte upload validation, OCR provider chain (Vision → EasyOCR → Tesseract), preprocessing, editable extraction preview | Confidence and warnings surfaced, never blocking |
| **5** | spaCy engine: normalisation with index mapping, lemma **and** surface matching, phrase matching, missing-term detection, 70/30 scoring, tiering, feedback generator | `engine_version` fingerprints the rubric, not just the code |
| **6** | Submission pipeline: typed and handwriting routes, `draft→scored` state machine, exactly-once scoring under a row lock, recoverable `failed` state, authenticated image streaming, history endpoints | A 503 never consumes an attempt |
| **7** | XP ledger, level curve, declarative achievement rules, tier badges, streaks, four materialised leaderboard scopes, administrative XP corrections | Scoring and awarding share one transaction |
| **8** | Class and platform analytics, vocabulary usage, score trends, student dashboard, four report types in CSV / Excel / PDF | Computed live; exports carry the screens' access rules |

### 1.3 What remains

| Sprint | Still to build | Depends on |
|---|---|---|
| **9** | Coverage gap closure, CI pipeline, load and edge-case passes | 8 |
| **10** | Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui, purple/blue/gold tokens, dark mode, typed API client, auth context and route protection | 9 |
| **11** | Landing, login, register (gender + avatar), student dashboard, practice page with live Chart.js, typed editor, handwriting upload with OCR preview, result page, profile, settings | 10 |
| **12** | Framer Motion reward sequences (crown + confetti / flower / hammer bonk-dizzy-fall-**recovery**), avatar components, sound manager honouring mute and `prefers-reduced-motion`, XP bar, level-up modal | 11 |
| **13** | Teacher dashboard, submission review, vocabulary manager, graph manager, export UI, leaderboard (4 scopes), analytics charts, admin user management | 12 |
| **14** | Full-stack compose, production Dockerfiles, VPS/Render/Railway/DigitalOcean guides, API docs, README, accessibility and responsive audit | 13 |

Roughly: **the backend is feature-complete and the frontend has not started.**
Every function in the specification — practising, marking, rewards, ranking,
analytics and exports — is reachable over the API today. None of it has a
screen. Sprint 9 hardens what exists; Sprints 10–14 build the interface.

### 1.4 Decisions still open

These are product calls, not technical blockers. Each has a working default in
place; say the word and it changes.

| # | Question | Current default |
|---|---|---|
| 1 | Should `/analysis/*` be readable by students, or stay teacher-only? | Teacher and admin only |
| 2 | NLTK is declared in `pyproject.toml` but unused since Sprint 5. Sprint 8 did not need it either — drop it? | Kept, unused |
| 3 | Editing a graph is open to any teacher; deleting it is owner-scoped. Should editing be owner-scoped too? | Any teacher may edit |
| 4 | Superseded handwriting uploads are retained when a student re-uploads, to avoid data loss on rollback. Orphan cleanup is unscheduled. | Left as an operational task for Sprint 14 |
| 5 | Publishing enforces "at least one required target", so a single-target graph makes the vocabulary percentage binary — 0% or 100%, hammer or crown. Enforce a minimum? | One target is enough |
| 6 | `analytics_snapshots` is deliberately unwritten — analytics are computed live. Archive periodic snapshots for the research record, or drop the table? | Kept, unused |
| 7 | A raw submission export is capped at 20,000 rows. Paginate a larger one, or leave date filters as the answer? | Capped, with the ceiling published on `/reports/capabilities` |

---

## 2. Gap analysis — existing docs vs. the product specification

The committed architecture set is internally coherent, but it describes a
meaningfully *different* product from the specification. These conflicts must be
resolved before any code is written, because each one changes the database
schema.

| # | Area | Existing docs say | Specification says | Resolution |
|---|---|---|---|---|
| 1 | **OCR target** | OCR runs on the **graph prompt image**, once per prompt, to read axis labels and legends | OCR runs on the **student's uploaded handwritten answer** | **Spec wins.** OCR moves from `graph_prompts` to `submissions`. This is the single largest change. |
| 2 | **User roles** | `learner`, `content_admin` | Student, Teacher, Administrator | **Spec wins.** Three roles: `student`, `teacher`, `admin`. |
| 3 | **Gender & avatars** | Not modelled at all | Gender selection drives a default cartoon avatar that receives rewards | **Add.** `users.gender` + `avatars` table. |
| 4 | **Vocabulary** | A `target_vocabulary` JSONB blob on each prompt | A first-class, teacher-editable vocabulary database with 7 categories and 25+ terms | **Add.** `vocabulary_categories` + `vocabulary_items` tables. |
| 5 | **Scoring weights** | Lexical 20% / Vocabulary 35% / Grammar 20% / Structure 25% | Vocabulary **70%** + Writing quality **30%** | **Spec wins.** The four doc metrics become sub-components of the 30% writing score. |
| 6 | **Reward tiers** | Not modelled | Crown / Flower / Hammer with titles, badges and animations | **Add.** See §4. |
| 7 | **Leaderboard scopes** | `daily`, `weekly`, `all_time` | Global, Class, Weekly, Monthly | **Spec wins.** Requires a new `classes` table. |
| 8 | **Teacher features** | Absent | Submission review, statistics, vocabulary reports, CSV/Excel/PDF export | **Add.** `teacher_reports` table + export service. |
| 9 | **Analytics** | Absent as a stored concern | Most/least used vocabulary, class averages, improvement trends, engagement | **Add.** `analytics_snapshots` table. |
| 10 | **OCR engine** | EasyOCR only | Google Vision → EasyOCR → Tesseract, in that preference order | **Spec wins.** Provider chain with availability detection. |

---

## 3. Resolved specification gaps

Four points in the specification are genuinely ambiguous or unworkable as
literally written. Each is resolved below, and the resolution is called out so it
can be overridden.

### 3.1 The missing 50–59% score band

The specification defines Crown at ≥90%, Flower at 60–89%, and Hammer at **below
50%**. Scores from **50% to 59%** fall into no band.

**Resolution:** a fourth tier is introduced rather than silently widening the
hammer band — dropping a comedy hammer on a student who scored 59% would be
demotivating and works against the stated "never humiliate" rule.

| Vocabulary % | Tier | Title | Badge | Animation |
|---|---|---|---|---|
| ≥ 90 | `crown` | Graph King / Graph Queen | Royal Vocabulary Master | Crown, sparkles, confetti, victory sound |
| 60 – 89 | `flower` | Rising Writer | Rising Writer | Rotating flower, positive sound |
| 50 – 59 | `steady` | Steady Learner | Steady Learner | Gentle nod + encouraging pulse, soft chime |
| < 50 | `hammer` | Keep Practicing! | Practice Needed | Cartoon hammer bonk, dizzy, fall, recovery |

### 3.2 What "Total Target Vocabulary" means

`Vocabulary % = (Detected / Total Target) × 100`.

If "Total Target" is the whole library (25+ terms), a student would need ~23
distinct terms in one paragraph to earn a crown. That is not achievable in a
150-word graph description, so **no student would ever see the crown animation** —
the centrepiece of the product.

**Resolution:** each graph carries a **curated target set of 8–12 terms** drawn
from the categories relevant to that chart (a pie chart needs comparison
language, not fluctuation language). The specification's formula is unchanged;
only its denominator is scoped per-graph. Implemented as a
`graph_target_vocabulary` join table, teacher-editable, with a sensible default
set derived from `graph_type` when a teacher has not curated one.

### 3.3 Synchronous analysis instead of a Redis/Celery worker queue

The existing docs put OCR and NLP behind a Redis-backed job queue with separate
worker containers.

**Resolution:** analysis runs **synchronously inside the API process**, behind a
`JobRunner` interface.

Rationale:
- The specification requires the extracted OCR text to be **previewed and
  confirmed by the student before analysis runs**. That is an inherently
  interactive, request-scoped flow — a fire-and-forget queue fights it.
- A queue adds Redis + two worker containers to the deployment. The
  specification targets Render/Railway/VPS deployment for an academic project;
  a 3-container stack (web, api, db) deploys on free tiers, a 6-container one
  does not.
- spaCy analysis of a 200-word paragraph takes milliseconds. Only OCR is slow
  (~1–3 s), and it is already an interactive step the student is waiting on.

The `JobRunner` abstraction keeps a Celery/RQ backend a drop-in change if
classroom load ever justifies it. This is a deliberate, documented reversal of
the committed architecture, not an oversight.

### 3.4 Google Vision requires paid credentials

Google Vision is first in the specified preference order but needs a billed GCP
account, which an academic prototype will usually not have.

**Resolution:** the OCR chain probes each provider's availability at startup and
falls through silently. **EasyOCR is the default working path**; Google Vision
activates automatically if credentials are present. The system is fully
functional with zero paid services.

---

## 4. Target data model

Eleven tables required by the specification, plus four supporting tables.

**Identity & access**
- `users` — email, password hash, full name, role, **gender**, avatar FK, class FK, XP, level, streak
- `avatars` — cartoon boy / cartoon girl variants, unlockable cosmetics
- `auth_sessions` — hashed refresh tokens, rotation, revocation
- `classes` — teacher-owned cohorts; required for the class leaderboard

**Content**
- `graphs` — line / bar / pie / area, difficulty, `chart_data` JSONB (rendered client-side by Chart.js, so no image assets are required), reference description
- `vocabulary_categories` — increase, decrease, fluctuation, stability, comparison, peak, lowest
- `vocabulary_items` — term, lemma, is_phrase, weight, active flag; teacher-editable
- `graph_target_vocabulary` — per-graph curated target set (see §3.2)

**Practice & evaluation**
- `submissions` — user, graph, input method (typed / handwriting), original image path, OCR text, OCR engine + confidence, final text, status
- `scores` — vocabulary score, writing score, final score, vocabulary %, detected/missing terms, category breakdown, reward tier, feedback

**Gamification**
- `xp_events` — append-only ledger; `users.total_xp` is a maintained cache
- `achievements` / `user_achievements` — declarative JSONB unlock rules
- `badges` / `user_badges` — Royal Vocabulary Master, Rising Writer, Steady Learner, Practice Needed
- `leaderboard_entries` — materialised rankings per scope (global / class / weekly / monthly)

**Reporting**
- `analytics_snapshots` — precomputed class and platform metrics
- `teacher_reports` — generated CSV / Excel / PDF export records

---

## 5. Scoring model

```
vocabulary_percentage = (unique target terms detected / total target terms) × 100
vocabulary_score      = min(vocabulary_percentage, 100)

writing_score         = weighted blend of:
                          word-count adequacy      25%
                          lexical diversity        25%
                          sentence structure       25%
                          overview presence        25%

final_score           = 0.70 × vocabulary_score + 0.30 × writing_score
reward_tier           = f(vocabulary_percentage)   ← per §3.1
```

The reward tier is driven by **vocabulary percentage**, not final score, because
the specification states the conditions in those terms ("90% or above vocabulary
usage").

**XP:** 20 per submission · +30 when `final_score ≥ 80` · +50 daily streak bonus
(once per calendar day) · plus each achievement's own reward.
**Levels:** 1–100, threshold `25 × (n−1) × n` — level 2 at 50 XP, level 100 at
247,500 XP.

---

## 6. Sprint plan

Fifteen sprints in dependency order. Each ends with a green build and a
conventional commit.

### Phase A — Design
| ✔ | Sprint | Deliverable |
|---|---|---|
| ✅ | **0** | This plan · SRS with functional/non-functional requirements · all 9 architecture docs realigned to §2 and §3 |

### Phase B — Backend (Phases 2 & 3 of the brief)
| ✔ | Sprint | Deliverable |
|---|---|---|
| ✅ | **1** | FastAPI skeleton, clean architecture layers, typed settings, SQLAlchemy 2.0 models, Alembic migrations, seed data, Dockerfile, Postgres compose, health checks |
| ✅ | **2** | JWT access + rotating refresh tokens, password hashing, RBAC dependencies, registration with gender→avatar assignment, profile endpoints, rate limiting |
| ✅ | **3** | Vocabulary CRUD (teacher-editable, 25+ seeded terms across 7 categories), graph CRUD with Chart.js data, per-graph target curation, class management |
| ✅ | **4** | Storage abstraction (local, S3-ready), upload validation with magic-byte checks, OCR provider chain, image preprocessing, extraction-preview endpoint |
| ✅ | **5** | spaCy + NLTK engine: normalisation, lemma matching, multi-word phrase matching, missing-vocabulary detection, scoring, feedback generator, report generator |
| ✅ | **6** | Submission pipeline: typed and handwriting flows, draft→extracted→scored state machine, preview-before-analysis, history endpoints |
| ✅ | **7** | Gamification: XP ledger, level curve, achievement rule engine, badge awards, streaks, four leaderboard scopes |
| ✅ | **8** | Analytics service, student/teacher dashboard aggregates, CSV/Excel/PDF export |
| ☐ | **9** | Pytest suite — unit, integration, API — targeting 80%+ coverage, plus CI |

### Phase C — Frontend (Phases 4 & 5 of the brief)
| ✔ | Sprint | Deliverable |
|---|---|---|
| ☐ | **10** | Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui, purple/blue/gold tokens, dark mode, typed API client, auth context and route protection |
| ☐ | **11** | Landing, login, register (gender + avatar), student dashboard, practice page with live Chart.js rendering, typed editor, handwriting upload with OCR preview, result page, profile, settings |
| ☐ | **12** | Framer Motion reward sequences (crown+confetti / flower / hammer bonk-dizzy-fall-recovery), avatar components, sound manager honouring mute and `prefers-reduced-motion`, XP bar, level-up modal |
| ☐ | **13** | Teacher dashboard, submission review, vocabulary manager, graph manager, export UI, leaderboard (4 scopes), analytics charts, admin user management |
| ☐ | **14** | Full-stack compose, production Dockerfiles, VPS/Render/Railway/DigitalOcean guides, API docs, README, accessibility and responsive audit |

---

## 7. Engineering standards

- **Python** — Black, Ruff, full type hints, Pytest. Clean architecture:
  routers → services → repositories. Dependency injection via FastAPI `Depends`.
- **TypeScript** — ESLint, Prettier, strict mode, no `any` in application code.
- **Commits** — Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`,
  `test:`, `chore:`), one sprint per logical group.
- **Secrets** — never committed. `.env.example` documents every variable;
  `.env` is git-ignored.
- **Validation** — Pydantic at every boundary; uploads validated by magic bytes,
  not file extension.

---

## 8. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| EasyOCR accuracy on messy handwriting | Wrong text → unfair score | Confidence surfaced to the student; the OCR preview is **editable** before analysis is run |
| EasyOCR model download size (~100 MB) | Slow first build | Models baked into the Docker image at build time, not fetched at runtime |
| spaCy model adds ~50 MB to the image | Slower deploys | `en_core_web_sm` pinned; installed at build time |
| Crown tier unreachable | Core feature never seen | Per-graph target sets (§3.2); calibrated with seed data |
| Hammer animation reads as mocking | Fails the "never humiliate" rule | Cartoon-only, self-recovering, always paired with encouragement; fully skippable |
| Coverage target slips late | Sprint 9 overruns | Tests written alongside each backend sprint, not deferred |

# GraphMaster

**AI-Powered Gamified Graph Description Learning Platform**

GraphMaster helps university students improve their graph-description writing in
academic English. A student is shown a chart, writes a description — typed or
photographed from handwriting — and receives a vocabulary-focused score with
animated gamified feedback, XP, achievements and leaderboard placement.

> **Status:** in development. See [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)
> for the sprint plan and current progress.

## How it works

1. The student picks a graph — line, bar, pie or area.
2. They describe it, by typing or by uploading a photo of handwriting.
3. Handwriting is transcribed by OCR, and the extracted text is shown for the
   student to correct before anything is scored.
4. An NLP engine detects graph-description vocabulary — lemma matching for
   single words, phrase matching for terms like *higher than* and *bottom out*.
5. The score is 70% vocabulary usage, 30% writing quality.
6. Vocabulary percentage selects a reward tier, which drives the animation:

   | Vocabulary % | Tier | Title |
   |---|---|---|
   | ≥ 90 | 👑 Crown | Graph King / Graph Queen |
   | 60–89 | 🌸 Flower | Rising Writer |
   | 50–59 | 🌱 Steady | Steady Learner |
   | < 50 | 🔨 Hammer | Keep Practicing! |

7. XP, achievements, badges and leaderboard standings update.

## Features

**Students** — practice across four chart types · typed or handwritten
submission · OCR with editable preview · vocabulary analysis with per-category
breakdown · animated rewards · XP and 100 levels · achievements and badges ·
four leaderboards · progress dashboard

**Teachers** — class management · submission review · class statistics ·
vocabulary usage reports · teacher-editable vocabulary library · graph authoring ·
CSV / Excel / PDF export

**Admins** — user and role management · platform analytics · full content control

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui · Framer Motion · Chart.js |
| Backend | FastAPI · Python 3.12 · SQLAlchemy 2.0 · Alembic |
| Database | PostgreSQL 16 |
| OCR | Google Vision → EasyOCR → Tesseract (fallback chain) |
| NLP | spaCy · NLTK |
| Deployment | Docker · docker-compose |

No paid service is required. EasyOCR is the default OCR path; Google Vision
activates automatically if credentials are present.

## Development

**Backend**

```bash
make install     # virtualenv, dependencies and the spaCy model
make migrate     # apply migrations
make seed        # reference data (idempotent)
make dev         # run the API with auto-reload on :8000
make test        # the suite with coverage
make perf        # the SRS performance budgets, excluded from `make test`
```

**Frontend**

```bash
make web-install # npm ci
make web-dev     # Next.js with hot reload on :3000
make web-check   # prettier, eslint, build, typecheck and tests
make api-types   # regenerate types/api.ts from a running API
```

`make check` runs both halves.

The API needs PostgreSQL 16 and a `SECRET_KEY`; copy `backend/.env.example` to
`backend/.env` and fill it in. The frontend needs `NEXT_PUBLIC_API_URL` —
`frontend/.env.example` to `frontend/.env.local`. `docker compose up` brings up
the database, the API and the web app together instead.

`NEXT_PUBLIC_*` is inlined into the browser bundle when the frontend is
**built**, not read from the environment at runtime, so in Docker it is a build
argument. Setting it only on the running container leaves every browser talking
to its own localhost.

### The typed API client

`frontend/types/api.ts` is generated from the backend's OpenAPI document, and
CI regenerates it and fails if the committed copy has drifted. Components never
call `fetch`: every request goes through `frontend/lib/api/`, which is where the
base URL, the bearer token, the error envelope and the refresh-and-retry live.

### Continuous integration

Every push runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | What it proves |
|---|---|
| Format and lint | `black` and `ruff` are clean |
| No committed secrets | No env or credential file is tracked, and no example file carries a real-looking value |
| Tests and coverage | The suite against a real PostgreSQL, with an 80% floor |
| Migrations | Upgrades from empty, matches the models, and round-trips a downgrade |
| Frontend | Prettier, ESLint, a production build, `tsc --noEmit` and the frontend tests |
| Generated types match the API | `types/api.ts` regenerated from the live OpenAPI document is unchanged |
| Compose file | `docker compose config` resolves |

`docker.yml` builds both images and boots them whenever the image inputs
change.

## Running it, and deploying it

Two separate documents, because they are two separate jobs:

- [`docs/RUNNING-LOCALLY.md`](docs/RUNNING-LOCALLY.md) — the whole stack on
  your own machine. Needs Docker and one command.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — the frontend on Vercel, the
  backend and PostgreSQL on Render, and the cross-site cookie problem you have
  to solve before login survives a reload.

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
docker compose up --build          # http://localhost:3000
```

The compose stack is for development. It is not what runs in production.

## Documentation

| Document | Contents |
|---|---|
| [Project plan](docs/PROJECT_PLAN.md) | Sprints, gap analysis, design decisions |
| [SRS](docs/00-srs.md) | Functional and non-functional requirements |
| [System architecture](docs/architecture/01-system-architecture.md) | Components, deployment |
| [Database schema](docs/architecture/02-database-schema.md) | Tables, constraints, indexes |
| [ER diagram](docs/architecture/03-er-diagram.md) | Entity relationships |
| [API design](docs/architecture/04-api-design.md) | REST contract |
| [Backend](docs/architecture/05-backend-architecture.md) | FastAPI internals |
| [Frontend](docs/architecture/06-frontend-architecture.md) | Next.js internals |
| [OCR](docs/architecture/07-ocr-architecture.md) | Provider chain, preprocessing |
| [NLP](docs/architecture/08-nlp-architecture.md) | Detection, scoring, feedback |
| [Gamification](docs/architecture/09-gamification-architecture.md) | XP, tiers, achievements |

Testing strategy, the API-surface invariants and the CI pipeline are described
in [Backend §10](docs/architecture/05-backend-architecture.md#10-testing).

## Licence

Academic research project.

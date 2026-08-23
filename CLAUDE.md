# GraphMaster — Project Context

AI-powered gamified graph-description learning platform for university students.

## Documentation map

Read these before changing anything structural:

| Document | Contents |
|---|---|
| `docs/PROJECT_PLAN.md` | Sprint plan, gap analysis, resolved spec ambiguities |
| `docs/00-srs.md` | Functional (FR-x) and non-functional (NFR-x) requirements |
| `docs/architecture/01-system-architecture.md` | Components and deployment |
| `docs/architecture/02-database-schema.md` | Full schema — **authoritative** |
| `docs/architecture/03-er-diagram.md` | ER diagram |
| `docs/architecture/04-api-design.md` | REST contract — **authoritative** |
| `docs/architecture/05-backend-architecture.md` | FastAPI internals |
| `docs/architecture/06-frontend-architecture.md` | Next.js internals |
| `docs/architecture/07-ocr-architecture.md` | OCR provider chain |
| `docs/architecture/08-nlp-architecture.md` | Analysis and scoring |
| `docs/architecture/09-gamification-architecture.md` | XP, tiers, achievements, leaderboard |

## Tech stack

**Backend** — FastAPI · Python 3.12 · SQLAlchemy 2.0 · Alembic · PostgreSQL 16 ·
spaCy · NLTK · EasyOCR · JWT
**Frontend** — Next.js 15 (App Router) · TypeScript · Tailwind · shadcn/ui ·
Framer Motion · Lottie · Chart.js · TanStack Query
**Deployment** — Docker · docker-compose

## Rules that are easy to get wrong

1. **Roles are `student`, `teacher`, `admin`.** Not `learner`/`content_admin` —
   early docs used those; they are obsolete.
2. **OCR runs on the student's handwritten answer**, never on the graph image.
   Graphs are structured `chart_data`, rendered by Chart.js.
3. **Scoring is 70% vocabulary + 30% writing quality.** Weights come from
   configuration, never hardcoded.
4. **The reward tier is driven by vocabulary percentage, not final score.**
5. **There are four tiers**: crown ≥90, flower 60–89, steady 50–59, hammer <50.
   The `steady` tier fills a gap the original spec left open — see
   PROJECT_PLAN §3.1.
6. **The OCR preview must stay editable** before analysis runs (FR-4.7).
7. **The hammer animation must always end in recovery** and always show
   "Keep Practicing! You Can Improve!" It must never read as humiliating.
8. **Sound is muted by default.**
9. **`xp_events` is append-only.** Corrections are offsetting entries, never
   edits or deletes.
10. **Vocabulary items are soft-deleted**, never removed — historical scores
    reference them.
11. **Never commit secrets.** `.env` is ignored; `.env.example` documents every
    variable.

## Conventions

- **Python** — Black, Ruff, full type hints. Routers → services → repositories;
  each layer calls only the one below it. Services raise domain exceptions,
  never `HTTPException`.
- **TypeScript** — strict mode, no `any` in application code. Components never
  call `fetch` directly; use `lib/api/`.
- **Commits** — Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`,
  `test:`, `chore:`).
- **Migrations** — Alembic, forward-only, hand-reviewed after autogeneration
  (autogenerate misses `CHECK` constraint and index-predicate changes, which
  this schema relies on).

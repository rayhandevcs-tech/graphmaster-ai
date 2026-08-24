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
12. **A graph cannot be published without at least one *required* target term.**
    Required targets are the denominator of the vocabulary percentage, so an
    empty set makes the exercise unscoreable.
13. **`is_phrase` is derived from the term, never sent by the client.** And
    editing a term does not re-derive a hand-set lemma — that would silently
    stop the term being detected.
14. **Vocabulary matching is lemma *and* surface.** spaCy's lemmatiser gets some
    terms wrong (`plateaued` → `plateaue`) and derivations are separate lemmas
    entirely (`fluctuation` is not `fluctuate`), so inflections and
    nominalisations generated from the target term are matched too. Variants are
    only ever generated **from a curated term**, never inferred from what the
    student wrote.
15. **Normalisation never lowercases or strips punctuation.** Case feeds the POS
    tagger and punctuation feeds sentence segmentation; matching is
    case-insensitive because it runs on token attributes. Every normalised
    character keeps an index back to the original so highlight offsets are real.
16. **`engine_version` fingerprints the rubric, not just the code.** Weights and
    thresholds are env config, so two scores could otherwise share a version and
    be incomparable.
17. **Feedback must never claim something the student did not do**, in either
    direction: no praise for unused vocabulary, and no "you used no X language"
    for a category they did use.
18. **Scoring is exactly-once.** `analyze` locks the submission row before
    reading its status. Two racing calls otherwise both score, one dies on the
    score's unique constraint, and both award XP for one piece of work.
19. **A scored submission is frozen**, and a *new* submission is how a student
    re-attempts a graph. Nothing is overwritten — improvement across attempts is
    the data the evaluation depends on.
20. **`failed` is recoverable, and `input_method` never flips.** A student can
    type into a submission whose recognition failed; the record must still show
    that handwriting was attempted and did not read.
21. **A 503 never consumes an attempt.** A missing language model or absent OCR
    engine is a deployment fault — nothing is written, and the same request
    works once the server is provisioned.
22. **Handwriting is streamed through an authenticated endpoint**, never a
    static path. Storage keys never appear in a response body.
23. **After a flush, re-read before serialising.** Columns with a server-side
    `onupdate` (`updated_at`) are expired by the flush, and relationships set
    by foreign key alone go stale in the identity map. Both surface as a lazy
    load that the async driver cannot service.

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

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
24. **`users.total_xp` is a cache and the ledger is the truth.** It is
    *recomputed* from `xp_events` after every award, never incremented — an
    award can be refused (the daily streak index, a lost achievement race), and
    a cache that adds up what it tried to award drifts a little further every
    time, with nothing to correct it.
25. **The streak bonus needs a streak of two.** A first submission and a
    submission that restarts a broken streak both earn nothing extra. Paying it
    on a reset day would reward breaking a streak as much as keeping one.
26. **Awards that a constraint may refuse run inside a savepoint.** The daily
    streak bonus, an achievement unlock and a badge award are each wrapped in
    `begin_nested()`. In PostgreSQL a failed statement poisons the whole
    transaction — and that transaction holds the student's score.
27. **A malformed achievement rule is inert, never fatal.** An unknown `type`
    unlocks nothing and is logged. A typo in a seed row must not cost a student
    the submission that happened to hit it.
28. **`class_id` is NULL for three of the four leaderboard scopes**, and NULLs
    do not compare equal — so `uq_leaderboard_entry` constrains the class board
    and nothing else. The partial index on `(scope, period_start, user_id)
    WHERE class_id IS NULL` is what stops a duplicated rebuild silently listing
    every student twice.
29. **`xp_events.created_at` uses `clock_timestamp()`, not `now()`.** One
    scoring appends up to four entries, and `now()` is the transaction
    timestamp — they would share a value and the ledger's order would fall back
    to a random UUID.
30. **Every gamification date comes from `PLATFORM_TIMEZONE`**, never the
    server's locale and never UTC unless that is what was configured. A cohort
    must roll over together.
31. **Leaderboards rank students only, and never publish a reward tier.** A
    hammer count belongs to one student's own results screen; on a board it is
    the humiliation FR-7.6 rules out.
32. **A missing average is `None`, never `0`.** A student who has not started
    is not one scoring nothing, and a zero sorts them below someone genuinely
    struggling.
33. **A class the caller does not teach is refused, not returned empty.** An
    empty report and a forbidden one look identical, and the first is a lie
    (FR-11.6).
34. **Vocabulary analytics count `scores.detected_terms`**, never a re-scan of
    the answer text. A second detector that disagrees with the first makes the
    figures unusable as evidence.
35. **Engagement is measured against enrolment**, so "half the class never
    started" cannot hide behind "everyone who practised, practised a lot".
36. **Analytics are computed live.** `analytics_snapshots` is unused on
    purpose — a cached figure is stale exactly when a teacher wants it, in the
    minutes after a lesson.
37. **A `UNIQUE` over nullable columns constrains nothing.** NULLs never
    compare equal, so use `NULLS NOT DISTINCT` or a partial index. Both
    `leaderboard_entries` and `analytics_snapshots` were wrong this way.
38. **CSV is always available; Excel and PDF are optional.** A missing library
    is a 503 and a `failed` report row, never a 500 — the same rule the OCR
    chain and the language model follow.
39. **A submission export carries scores and metadata, never the answers.** A
    file circulated by email should not hold every student's writing verbatim.
40. **Excel cannot store a timezone.** Convert to `PLATFORM_TIMEZONE`, drop the
    offset, and name the zone in the report header.

41. **A new route is guarded until the allowlist says otherwise.**
    `tests/api/test_api_surface.py` walks the published OpenAPI document and
    requires every operation to refuse an unauthenticated caller — and to
    refuse it *for want of a token*, not merely to answer 401 for reasons of
    its own. Making a route public means adding a line, with a reason, to
    `PUBLIC` in that file.
42. **An optional dependency gets a fake, never a mock.** `boto3`,
    `google-cloud-vision` and `easyocr` are not installed by default. A mock
    agrees with whatever the code does, including calling `get_object` with
    the wrong keyword; a fake with the real signatures disagrees.
43. **Coverage of code nobody calls is a false signal.** Dead code is deleted,
    not tested, and `__repr__` is excluded in `pyproject.toml` rather than
    asserted on. A number lifted by exercising something no caller reaches
    measures nothing.
44. **`configure_logging()` clears the root handlers**, pytest's capture
    handler included. A test that triggers it reads stdout rather than
    `caplog`, and puts the handlers back — otherwise every later test in the
    session logs into nothing.
45. **`app.db.session.engine` pools connections across event loops.** Each
    test gets its own loop, so a test that uses the process-wide engine must
    `await engine.dispose(close=False)` around itself. Closing them instead
    fails from the wrong loop.
46. **One pytest session at a time.** The session-scoped `database_schema`
    fixture drops and recreates every table, so a second run started against
    the same database pulls the schema out from under the first — and the
    resulting errors point at the tests, not at the collision.
47. **NFR-1.1's fifty concurrent users describes a deployment**, not the test
    harness: one worker sharing a core with the client cannot reproduce it.
    The 500 ms budget is asserted per request, plus a service-time ceiling
    under fifty concurrent callers, which is what actually catches an N+1 or a
    lock held across I/O.

48. **`frontend/types/api.ts` is generated, never edited.** It is rendered from
    the backend's OpenAPI document by `scripts/generate-api-types.mjs`; run
    `make api-types` against a running API. CI regenerates it and fails on any
    diff, so a hand-edit is reverted by the next build.
49. **`NEXT_PUBLIC_*` is inlined when the frontend is *built*.** The browser has
    no `process.env`. In Docker it is a build argument; set only on the running
    container it is silently absent, and every user's browser falls back to
    talking to its own localhost.
50. **The access token lives in memory in the browser.** Not `localStorage`,
    not a readable cookie — both turn one XSS bug into a stolen token — and
    never in server-side module state, which is shared by every request the
    Node process handles. A hard refresh legitimately starts with none; the
    bootstrap refresh is what recovers the session.
51. **One refresh at a time, and exactly one retry.** Concurrent 401s must
    share a single refresh: rotating the refresh token twice looks like theft
    to the backend, which revokes the whole session family. And a refresh that
    fails only signs someone out if they *had* a session — a visitor who never
    signed in must not be bounced off the landing page.
52. **Gold is reserved for the crown tier, XP and level-ups.** It is a separate
    token from shadcn's `--accent`, which is the neutral hover surface;
    mapping the two together puts gold on every menu item and spends the one
    colour that makes a crown feel earned. `tests/design-tokens.test.ts`
    enforces it with an allowlist.
53. **Every colour is a token defined for both themes**, and there is no
    hardcoded hex outside `app/globals.css` — the same test fails the build.
    There is no `tailwind.config`; Tailwind 4 keeps the theme in the
    stylesheet under `@theme`.
54. **Route protection in the browser is UX, not a security boundary.** The API
    checks every token and every role, and the surface test proves it. The
    guard cannot run in middleware because neither credential reaches a Next
    server: the access token is in the tab's memory and the refresh cookie
    belongs to the API's origin.
55. **A wrong role is a dead end, not a redirect.** Bouncing a student off a
    teacher URL leaves them wondering whether they mistyped; the page says so
    and offers the way back.
56. **`next build` runs before `tsc --noEmit`.** The build generates
    `next-env.d.ts`, which declares the ambient types for CSS imports and
    `next/font`. Typechecking a clean checkout without it fails on imports
    that are fine.

## Conventions

- **Python** — Black, Ruff, full type hints. Routers → services → repositories;
  each layer calls only the one below it. Services raise domain exceptions,
  never `HTTPException`.
- **TypeScript** — strict mode, no `any` in application code. Components never
  call `fetch` directly; use `lib/api/`, one module per resource over the
  shared client. Prettier and ESLint (`next/core-web-vitals` +
  `next/typescript`) are enforced by CI, as is a production build.
- **Commits** — Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`,
  `test:`, `chore:`).
- **Migrations** — Alembic, forward-only, hand-reviewed after autogeneration
  (autogenerate misses `CHECK` constraint and index-predicate changes, which
  this schema relies on).

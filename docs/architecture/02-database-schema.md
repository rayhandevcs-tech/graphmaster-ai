# Database Schema

## 1. Overview

GraphMaster AI uses **PostgreSQL** as its single system of record. The schema is organized into four functional groups:

1. **Identity** — users, auth sessions
2. **Content** — graph prompts (the exercises)
3. **Submissions & Analysis** — learner responses, OCR extractions, NLP scoring
4. **Gamification** — XP ledger, achievements, leaderboard

See [03-er-diagram.md](./03-er-diagram.md) for the visual entity-relationship diagram of everything defined here.

Conventions used throughout:
- All primary keys are `UUID` (`gen_random_uuid()`), avoiding sequential-ID enumeration and simplifying multi-service inserts (e.g., workers writing results independently of the API).
- All tables include `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; mutable tables also include `updated_at TIMESTAMPTZ`.
- Foreign keys use `ON DELETE RESTRICT` by default unless otherwise noted, to prevent silent data loss; append-only ledgers (`xp_events`) never allow deletes.

## 2. Identity

### 2.1 `users`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | |
| email | CITEXT | UNIQUE, NOT NULL | Case-insensitive |
| password_hash | TEXT | NOT NULL | Argon2/bcrypt hash |
| display_name | TEXT | NOT NULL | |
| role | TEXT | NOT NULL, CHECK IN ('learner','content_admin') | Default `'learner'` |
| avatar_url | TEXT | NULL | |
| current_level | INTEGER | NOT NULL, DEFAULT 1 | Denormalized from XP for fast reads; see [09-gamification-architecture.md](./09-gamification-architecture.md) |
| total_xp | BIGINT | NOT NULL, DEFAULT 0 | Denormalized cache of `SUM(xp_events.amount)` |
| current_streak_days | INTEGER | NOT NULL, DEFAULT 0 | |
| longest_streak_days | INTEGER | NOT NULL, DEFAULT 0 | |
| last_activity_date | DATE | NULL | Drives streak calculation |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (email)`; `INDEX (total_xp DESC)` to support leaderboard fallback queries.

### 2.2 `auth_sessions`

Tracks issued refresh tokens for revocation support (JWT access tokens remain stateless).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL, ON DELETE CASCADE | |
| refresh_token_hash | TEXT | UNIQUE, NOT NULL | Hashed, never stored raw |
| user_agent | TEXT | NULL | |
| ip_address | INET | NULL | |
| expires_at | TIMESTAMPTZ | NOT NULL | |
| revoked_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `INDEX (user_id)`, `INDEX (expires_at)`.

## 3. Content

### 3.1 `graph_prompts`

The chart/graph exercises learners describe.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| title | TEXT | NOT NULL | |
| chart_type | TEXT | NOT NULL, CHECK IN ('bar','line','pie','table','process','mixed') | |
| difficulty | TEXT | NOT NULL, CHECK IN ('beginner','intermediate','advanced') | |
| image_url | TEXT | NOT NULL | Object storage reference |
| reference_description | TEXT | NULL | Model answer, used for NLP comparison baselines |
| target_vocabulary | JSONB | NOT NULL, DEFAULT '[]' | Curated word list expected in a strong answer |
| tags | TEXT[] | NOT NULL, DEFAULT '{}' | e.g. `{trend, comparison, IELTS-Task1}` |
| is_published | BOOLEAN | NOT NULL, DEFAULT false | |
| created_by | UUID | FK → users.id, NOT NULL | Must be a `content_admin` |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `INDEX (chart_type, difficulty)`, `INDEX (is_published)`, GIN index on `tags`.

## 4. Submissions & Analysis

### 4.1 `submissions`

A single learner attempt at describing a `graph_prompt`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| graph_prompt_id | UUID | FK → graph_prompts.id, NOT NULL | |
| response_text | TEXT | NOT NULL | Learner's written description |
| word_count | INTEGER | NOT NULL | |
| status | TEXT | NOT NULL, CHECK IN ('pending','ocr_processing','nlp_processing','scored','failed') | Default `'pending'` |
| overall_score | NUMERIC(5,2) | NULL | Composite score once `scored` |
| submitted_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| scored_at | TIMESTAMPTZ | NULL | |

Index: `INDEX (user_id, submitted_at DESC)`, `INDEX (graph_prompt_id)`, `INDEX (status)`.

### 4.2 `ocr_extractions`

One row per OCR job run against a `graph_prompt` image (cached/reused across submissions of the same prompt).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| graph_prompt_id | UUID | FK → graph_prompts.id, NOT NULL | |
| raw_text_blocks | JSONB | NOT NULL | Array of `{text, bbox, confidence}` per [07-ocr-architecture.md](./07-ocr-architecture.md) |
| structured_labels | JSONB | NULL | Parsed axis/legend/title labels |
| engine_version | TEXT | NOT NULL | EasyOCR model/version used |
| status | TEXT | NOT NULL, CHECK IN ('processing','completed','failed') | |
| error_message | TEXT | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `INDEX (graph_prompt_id)`.

### 4.3 `nlp_analyses`

One row per NLP scoring job run against a `submission`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| submission_id | UUID | FK → submissions.id, UNIQUE, NOT NULL, ON DELETE CASCADE | |
| lexical_diversity_score | NUMERIC(5,2) | NOT NULL | Type-token ratio derived metric |
| academic_vocabulary_score | NUMERIC(5,2) | NOT NULL | Coverage of academic word list |
| target_vocabulary_hits | JSONB | NOT NULL | Which `graph_prompts.target_vocabulary` terms were used |
| grammar_signal_score | NUMERIC(5,2) | NOT NULL | Structural/grammar heuristic score |
| structure_score | NUMERIC(5,2) | NOT NULL | Overview/trend/detail paragraph structure adherence |
| feedback_summary | TEXT | NOT NULL | Human-readable generated feedback |
| engine_version | TEXT | NOT NULL | spaCy pipeline/model version used |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (submission_id)`.

See [08-nlp-architecture.md](./08-nlp-architecture.md) for how each score is computed and rolled up into `submissions.overall_score`.

## 5. Gamification

### 5.1 `xp_events`

**Append-only ledger.** Every XP-earning action creates a row; `users.total_xp` is a maintained cache of the sum. Never updated or deleted — corrections are issued as new offsetting events.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| amount | INTEGER | NOT NULL | Positive (or negative for penalties/reversals) |
| reason | TEXT | NOT NULL, CHECK IN ('submission_scored','daily_streak','achievement_unlocked','manual_adjustment') | |
| source_submission_id | UUID | FK → submissions.id, NULL | Populated when reason = `submission_scored` |
| source_achievement_id | UUID | FK → achievements.id, NULL | Populated when reason = `achievement_unlocked` |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `INDEX (user_id, created_at DESC)`.

### 5.2 `achievements`

Catalog of unlockable achievements (static reference data).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| code | TEXT | UNIQUE, NOT NULL | Stable identifier, e.g. `first_submission` |
| title | TEXT | NOT NULL | |
| description | TEXT | NOT NULL | |
| icon_url | TEXT | NULL | |
| xp_reward | INTEGER | NOT NULL, DEFAULT 0 | |
| unlock_rule | JSONB | NOT NULL | Declarative trigger rule, see [09-gamification-architecture.md](./09-gamification-architecture.md) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 5.3 `user_achievements`

Join table recording which users unlocked which achievements, and when.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| achievement_id | UUID | FK → achievements.id, NOT NULL | |
| unlocked_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (user_id, achievement_id)`.

### 5.4 `leaderboard_snapshots`

Periodic materialized rankings, avoiding an expensive `ORDER BY total_xp` scan on every leaderboard page view.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| period | TEXT | NOT NULL, CHECK IN ('daily','weekly','all_time') | |
| period_start | DATE | NOT NULL | |
| user_id | UUID | FK → users.id, NOT NULL | |
| rank | INTEGER | NOT NULL | |
| xp_in_period | BIGINT | NOT NULL | |
| generated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (period, period_start, user_id)`, `INDEX (period, period_start, rank)`.

## 6. Referential Integrity Summary

- `submissions.user_id` / `graph_prompt_id` → `RESTRICT` (a submission must never outlive its author or prompt reference silently).
- `nlp_analyses.submission_id` → `CASCADE` (an analysis has no meaning without its submission).
- `xp_events` → no cascading deletes permitted on `user_id`; user deletion is a soft-delete (`users.deleted_at`, not modeled above but implied by data-retention policy) to preserve ledger integrity.
- `user_achievements` enforces one unlock per user per achievement via the unique constraint.

## 7. Migration Strategy

Schema changes are managed through versioned, forward-only migrations (e.g., Alembic for the FastAPI backend). Each migration is reviewed for backward compatibility with the currently deployed API version to support zero-downtime rolling deploys, per the deployment topology in [01-system-architecture.md](./01-system-architecture.md).

# Database Schema

> **Revision 2.0** — realigned to the product specification. See
> [../PROJECT_PLAN.md](../PROJECT_PLAN.md) §2 for the full list of changes from
> revision 1.0 and the reasoning behind each.

## 1. Overview

GraphMaster uses **PostgreSQL 16** as its single system of record. The schema is
organised into five functional groups:

1. **Identity & access** — users, avatars, sessions, classes
2. **Content** — graphs, vocabulary library, per-graph targets
3. **Practice & evaluation** — submissions, scores
4. **Gamification** — XP ledger, achievements, badges, leaderboard
5. **Reporting** — analytics snapshots, teacher reports

See [03-er-diagram.md](./03-er-diagram.md) for the visual companion.

### Conventions

- Primary keys are `UUID` defaulting to `gen_random_uuid()`, avoiding sequential
  enumeration of student records.
- Every table carries `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; mutable
  tables also carry `updated_at`.
- Enumerated values are enforced with `CHECK` constraints rather than PostgreSQL
  `ENUM` types, so adding a value is an ordinary migration rather than a type
  alteration that locks the table.
- Monetary-style precision is not needed; all scores are `NUMERIC(5,2)`, giving
  a range of `-999.99` to `999.99` with exact decimal semantics (never floats,
  which would make score equality comparisons unreliable).
- Foreign keys default to `ON DELETE RESTRICT`. Exceptions are called out
  individually.

---

## 2. Identity & access

### 2.1 `users`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | |
| email | CITEXT | UNIQUE, NOT NULL | Case-insensitive |
| password_hash | TEXT | NOT NULL | bcrypt |
| full_name | TEXT | NOT NULL | |
| role | TEXT | NOT NULL, DEFAULT `'student'`, CHECK IN (`'student'`,`'teacher'`,`'admin'`) | |
| gender | TEXT | NOT NULL, CHECK IN (`'male'`,`'female'`) | Drives default avatar (FR-2.2) |
| avatar_id | UUID | FK → avatars.id, NULL | Assigned at registration |
| class_id | UUID | FK → classes.id, NULL, ON DELETE SET NULL | Students only |
| total_xp | BIGINT | NOT NULL, DEFAULT 0 | Cache of `SUM(xp_events.amount)` |
| current_level | INTEGER | NOT NULL, DEFAULT 1, CHECK BETWEEN 1 AND 100 | Derived from `total_xp` |
| current_streak_days | INTEGER | NOT NULL, DEFAULT 0 | |
| longest_streak_days | INTEGER | NOT NULL, DEFAULT 0 | |
| last_activity_date | DATE | NULL | Drives streak evaluation |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft deactivation |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `UNIQUE (email)`, `INDEX (role)`, `INDEX (class_id)`,
`INDEX (total_xp DESC)`.

`total_xp` and `current_level` are deliberately denormalised caches. Every
profile page, leaderboard row and level badge needs them, and recomputing
`SUM(xp_events.amount)` on each read would make the leaderboard a full scan of
the ledger. Both are written in the same transaction as the ledger insert, so
they cannot drift; if they ever do, the ledger is authoritative and both are
recomputable.

### 2.2 `avatars`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| code | TEXT | UNIQUE, NOT NULL | e.g. `boy_default`, `girl_default` |
| name | TEXT | NOT NULL | Display name |
| gender | TEXT | NOT NULL, CHECK IN (`'male'`,`'female'`) | |
| image_url | TEXT | NOT NULL | Storage reference |
| is_default | BOOLEAN | NOT NULL, DEFAULT false | Exactly one per gender |
| unlock_level | INTEGER | NOT NULL, DEFAULT 1 | Cosmetic progression (FR-2.5) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `INDEX (gender, is_default)`. Partial unique index enforcing one default
per gender: `CREATE UNIQUE INDEX ON avatars (gender) WHERE is_default`.

### 2.3 `classes`

Cohorts owned by a teacher. Required by the class leaderboard (FR-9.2) and by
teacher access scoping (FR-11.6).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| name | TEXT | NOT NULL | e.g. "ENG-201 Section B" |
| code | TEXT | UNIQUE, NOT NULL | Join code |
| description | TEXT | NULL | |
| teacher_id | UUID | FK → users.id, NOT NULL | Must have role `teacher` or `admin` |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `UNIQUE (code)`, `INDEX (teacher_id)`.

### 2.4 `auth_sessions`

Refresh-token records, enabling revocation while access tokens stay stateless.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL, ON DELETE CASCADE | |
| refresh_token_hash | TEXT | UNIQUE, NOT NULL | SHA-256; raw token never stored |
| user_agent | TEXT | NULL | |
| ip_address | INET | NULL | |
| expires_at | TIMESTAMPTZ | NOT NULL | |
| revoked_at | TIMESTAMPTZ | NULL | Set on logout or rotation |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `INDEX (user_id)`, `INDEX (expires_at)`.

---

## 3. Content

### 3.1 `graphs`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| title | TEXT | NOT NULL | |
| prompt | TEXT | NOT NULL | Instruction shown to the student |
| graph_type | TEXT | NOT NULL, CHECK IN (`'line'`,`'bar'`,`'pie'`,`'area'`) | FR-3.1 |
| difficulty | TEXT | NOT NULL, CHECK IN (`'beginner'`,`'intermediate'`,`'advanced'`) | |
| chart_data | JSONB | NOT NULL | Chart.js-compatible dataset — see §3.2 |
| image_url | TEXT | NULL | Optional fallback raster |
| reference_description | TEXT | NULL | Model answer shown after submission |
| is_published | BOOLEAN | NOT NULL, DEFAULT false | |
| created_by | UUID | FK → users.id, NOT NULL | Teacher or admin |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `INDEX (graph_type, difficulty)`, `INDEX (is_published)`.

### 3.2 Why `chart_data` and not an image

Storing charts as structured data rather than PNGs (FR-3.2) means:

- Charts render crisply at any viewport and in dark mode, which a baked-in
  raster with a white background cannot do.
- Teachers author a graph by entering numbers, with no image editor involved.
- Screen readers can be given a real data table alternative (NFR-4.5), which is
  impossible for a flat image.
- No object storage is needed for content, only for student uploads.

Shape:

```json
{
  "labels": ["2019", "2020", "2021", "2022", "2023"],
  "datasets": [
    { "label": "Solar", "data": [12, 19, 27, 41, 58] },
    { "label": "Wind",  "data": [30, 33, 36, 38, 40] }
  ],
  "x_axis_label": "Year",
  "y_axis_label": "Energy output (TWh)",
  "unit": "TWh"
}
```

### 3.3 `vocabulary_categories`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| code | TEXT | UNIQUE, NOT NULL | `increase`, `decrease`, `fluctuation`, `stability`, `comparison`, `peak`, `lowest` |
| name | TEXT | NOT NULL | Display name |
| description | TEXT | NULL | |
| display_order | INTEGER | NOT NULL, DEFAULT 0 | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 3.4 `vocabulary_items`

The teacher-editable vocabulary library (FR-5.1, FR-5.4).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| category_id | UUID | FK → vocabulary_categories.id, NOT NULL | |
| term | TEXT | NOT NULL | Surface form, e.g. `bottom out` |
| lemma | TEXT | NOT NULL | Normalised match key, e.g. `bottom out` |
| is_phrase | BOOLEAN | NOT NULL, DEFAULT false | True when the term contains whitespace |
| weight | NUMERIC(3,2) | NOT NULL, DEFAULT 1.00 | Allows advanced terms to count for more |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete, preserving historical scores |
| created_by | UUID | FK → users.id, NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `UNIQUE (lemma)`, `INDEX (category_id)`, `INDEX (is_active)`.

Vocabulary items are **soft-deleted** rather than removed. A hard delete would
orphan the term references stored inside historical `scores.detected_terms`,
making a student's past result unexplainable.

### 3.5 `graph_target_vocabulary`

The curated per-graph target set that forms the denominator of the vocabulary
percentage (FR-5.5). See [../PROJECT_PLAN.md](../PROJECT_PLAN.md) §3.2 for why
the target set is scoped per graph rather than to the whole library.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| graph_id | UUID | FK → graphs.id, NOT NULL, ON DELETE CASCADE | |
| vocabulary_item_id | UUID | FK → vocabulary_items.id, NOT NULL | |
| is_required | BOOLEAN | NOT NULL, DEFAULT true | Optional terms are credited but not counted in the denominator |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (graph_id, vocabulary_item_id)`.

When a graph has no rows here, the analysis service falls back to a default set
derived from `graph_type` (FR-5.6): pie charts draw on comparison, peak and
lowest; line and area charts draw on increase, decrease, fluctuation and
stability; bar charts draw on comparison, increase and decrease.

---

## 4. Practice & evaluation

### 4.1 `submissions`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| graph_id | UUID | FK → graphs.id, NOT NULL | |
| input_method | TEXT | NOT NULL, CHECK IN (`'typed'`,`'handwriting'`) | |
| answer_text | TEXT | NULL | Final text analysed; NULL until extraction completes |
| original_image_path | TEXT | NULL | Set for `handwriting` |
| ocr_text | TEXT | NULL | Raw OCR output, preserved even after student edits |
| ocr_provider | TEXT | NULL, CHECK IN (`'google_vision'`,`'easyocr'`,`'tesseract'`) | FR-4.8 |
| ocr_confidence | NUMERIC(5,4) | NULL | 0.0000–1.0000 |
| was_ocr_edited | BOOLEAN | NOT NULL, DEFAULT false | True when the student corrected the extraction (FR-4.7) |
| word_count | INTEGER | NOT NULL, DEFAULT 0 | |
| status | TEXT | NOT NULL, DEFAULT `'draft'`, CHECK IN (`'draft'`,`'extracting'`,`'extracted'`,`'analyzing'`,`'scored'`,`'failed'`) | |
| error_message | TEXT | NULL | Populated when `status = 'failed'` (NFR-3.2) |
| submitted_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| scored_at | TIMESTAMPTZ | NULL | |

Indexes: `INDEX (user_id, submitted_at DESC)`, `INDEX (graph_id)`,
`INDEX (status)`.

Both `ocr_text` and `answer_text` are kept. `ocr_text` is the unmodified machine
output and `answer_text` is what was actually scored; keeping both is what makes
OCR accuracy measurable as research data, which matters for an academic project.

### 4.2 Submission state machine

```
                    typed
  ┌──────┐  ───────────────────────────────►  ┌───────────┐
  │ draft│                                     │ analyzing │
  └──┬───┘  ──────────►┌────────────┐          └─────┬─────┘
     │   handwriting   │ extracting │                │
     │                 └─────┬──────┘                ▼
     │                       │                  ┌────────┐
     │                       ▼                  │ scored │
     │                 ┌───────────┐            └────────┘
     │                 │ extracted │──────────────►┃
     │                 └───────────┘   student confirms text
     │                       │
     └───────────────────────┴──────────────► ┌────────┐
                        on error              │ failed │
                                              └────────┘
```

`extracted` is a real, persisted state rather than a transient one, because
FR-4.6 requires the student to review the OCR output before analysis runs. The
submission legitimately waits there for human input.

### 4.3 `scores`

One row per scored submission.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| submission_id | UUID | FK → submissions.id, UNIQUE, NOT NULL, ON DELETE CASCADE | |
| vocabulary_score | NUMERIC(5,2) | NOT NULL | 0–100 |
| writing_score | NUMERIC(5,2) | NOT NULL | 0–100 |
| final_score | NUMERIC(5,2) | NOT NULL | `0.70 × vocabulary + 0.30 × writing` (FR-6.8) |
| vocabulary_percentage | NUMERIC(5,2) | NOT NULL | Drives the reward tier |
| detected_count | INTEGER | NOT NULL | Total occurrences |
| unique_detected_count | INTEGER | NOT NULL | Distinct terms |
| total_target_count | INTEGER | NOT NULL | Denominator at scoring time |
| detected_terms | JSONB | NOT NULL, DEFAULT `'[]'` | `[{term, category, count, positions}]` |
| missing_terms | JSONB | NOT NULL, DEFAULT `'[]'` | `[{term, category}]` (FR-6.5) |
| category_breakdown | JSONB | NOT NULL, DEFAULT `'{}'` | Per-category hit/target counts (FR-6.11) |
| writing_breakdown | JSONB | NOT NULL, DEFAULT `'{}'` | Sub-scores for the 30% component |
| reward_tier | TEXT | NOT NULL, CHECK IN (`'crown'`,`'flower'`,`'steady'`,`'hammer'`) | FR-7.1 |
| feedback | JSONB | NOT NULL, DEFAULT `'{}'` | Generated feedback payload (FR-6.10) |
| engine_version | TEXT | NOT NULL | Analysis engine version for reproducibility |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (submission_id)`, `INDEX (reward_tier)`,
`INDEX (final_score DESC)`.

`total_target_count` is stored on the row rather than looked up from
`graph_target_vocabulary` at read time. A teacher may add a target term next
week; without this column, every historical percentage for that graph would
silently change, which would corrupt the improvement-trend analytics (FR-12.4).

---

## 5. Gamification

### 5.1 `xp_events`

**Append-only ledger** (NFR-3.3). Never updated, never deleted; corrections are
issued as offsetting entries.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| amount | INTEGER | NOT NULL | May be negative for corrections |
| reason | TEXT | NOT NULL, CHECK IN (`'submission'`,`'high_score_bonus'`,`'streak_bonus'`,`'achievement'`,`'manual_adjustment'`) | |
| submission_id | UUID | FK → submissions.id, NULL | |
| achievement_id | UUID | FK → achievements.id, NULL | |
| note | TEXT | NULL | Required for `manual_adjustment` |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `INDEX (user_id, created_at DESC)`, `INDEX (reason)`.

Partial unique index preventing a duplicate daily streak award (FR-8.3):
`CREATE UNIQUE INDEX ON xp_events (user_id, (created_at::date)) WHERE reason = 'streak_bonus'`.

### 5.2 `achievements`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| code | TEXT | UNIQUE, NOT NULL | e.g. `first_submission` |
| title | TEXT | NOT NULL | |
| description | TEXT | NOT NULL | |
| icon | TEXT | NOT NULL | Emoji or icon key |
| xp_reward | INTEGER | NOT NULL, DEFAULT 0 | |
| rule | JSONB | NOT NULL | Declarative unlock condition (FR-8.9) |
| display_order | INTEGER | NOT NULL, DEFAULT 0 | |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 5.3 `user_achievements`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| achievement_id | UUID | FK → achievements.id, NOT NULL | |
| submission_id | UUID | FK → submissions.id, NULL | The submission that triggered it |
| unlocked_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (user_id, achievement_id)` — enforces FR-8.8 at the database
level rather than trusting application logic.

### 5.4 `badges`

Tier badges, distinct from achievements: a badge is re-awardable per submission
and reflects performance on that attempt, whereas an achievement is a permanent
one-time milestone.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| code | TEXT | UNIQUE, NOT NULL | `royal_vocabulary_master`, `rising_writer`, `steady_learner`, `practice_needed` |
| name | TEXT | NOT NULL | |
| description | TEXT | NOT NULL | |
| icon | TEXT | NOT NULL | |
| reward_tier | TEXT | NOT NULL, CHECK IN (`'crown'`,`'flower'`,`'steady'`,`'hammer'`) | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (reward_tier)`.

### 5.5 `user_badges`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| badge_id | UUID | FK → badges.id, NOT NULL | |
| submission_id | UUID | FK → submissions.id, NOT NULL | |
| awarded_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `UNIQUE (submission_id)` — one badge per submission —
`INDEX (user_id, awarded_at DESC)`.

### 5.6 `leaderboard_entries`

Materialised rankings (NFR-1.4), covering the four scopes of FR-9.1 – FR-9.3.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| scope | TEXT | NOT NULL, CHECK IN (`'global'`,`'class'`,`'weekly'`,`'monthly'`) | |
| class_id | UUID | FK → classes.id, NULL, ON DELETE CASCADE | Set only when `scope = 'class'` |
| period_start | DATE | NOT NULL | Epoch date for `global` |
| period_end | DATE | NOT NULL | |
| user_id | UUID | FK → users.id, NOT NULL, ON DELETE CASCADE | |
| rank | INTEGER | NOT NULL | |
| xp | BIGINT | NOT NULL | XP within the period |
| average_score | NUMERIC(5,2) | NOT NULL, DEFAULT 0 | Tie-breaker (FR-9.4) |
| submission_count | INTEGER | NOT NULL, DEFAULT 0 | |
| achievement_count | INTEGER | NOT NULL, DEFAULT 0 | Second tie-breaker |
| generated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Indexes: `UNIQUE (scope, class_id, period_start, user_id)`,
`INDEX (scope, class_id, period_start, rank)`.

A `CHECK` constraint enforces the scope/class relationship:
`CHECK ((scope = 'class') = (class_id IS NOT NULL))`.

---

## 6. Reporting

### 6.1 `analytics_snapshots`

Precomputed metrics backing FR-12.1 – FR-12.5.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| scope | TEXT | NOT NULL, CHECK IN (`'platform'`,`'class'`,`'student'`) | |
| class_id | UUID | FK → classes.id, NULL, ON DELETE CASCADE | |
| user_id | UUID | FK → users.id, NULL, ON DELETE CASCADE | |
| period_start | DATE | NOT NULL | |
| period_end | DATE | NOT NULL | |
| metrics | JSONB | NOT NULL | See §6.2 |
| generated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Index: `UNIQUE (scope, class_id, user_id, period_start)`.

### 6.2 `metrics` payload shape

```json
{
  "submission_count": 412,
  "active_student_count": 38,
  "average_final_score": 71.4,
  "average_vocabulary_percentage": 64.2,
  "most_used_vocabulary":  [{"term": "increase", "count": 301}],
  "least_used_vocabulary": [{"term": "oscillate", "count": 4}],
  "reward_tier_distribution": {"crown": 22, "flower": 190, "steady": 88, "hammer": 112},
  "score_trend": [{"date": "2026-08-01", "average": 64.1}],
  "engagement": {"submissions_per_active_student": 10.8, "streak_holders": 14}
}
```

Analytics are stored as JSONB rather than as wide columns because the metric set
is expected to grow throughout the research phase, and adding a metric should
not require a migration on a table that already holds historical rows.

### 6.3 `teacher_reports`

Generated export records (FR-11.5).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| teacher_id | UUID | FK → users.id, NOT NULL | |
| class_id | UUID | FK → classes.id, NULL, ON DELETE CASCADE | |
| report_type | TEXT | NOT NULL, CHECK IN (`'class_summary'`,`'student_detail'`,`'vocabulary_usage'`,`'submission_export'`) | |
| format | TEXT | NOT NULL, CHECK IN (`'csv'`,`'xlsx'`,`'pdf'`) | |
| parameters | JSONB | NOT NULL, DEFAULT `'{}'` | Date range, filters |
| file_path | TEXT | NULL | Storage reference once generated |
| status | TEXT | NOT NULL, DEFAULT `'pending'`, CHECK IN (`'pending'`,`'ready'`,`'failed'`) | |
| error_message | TEXT | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| completed_at | TIMESTAMPTZ | NULL | |

Index: `INDEX (teacher_id, created_at DESC)`.

---

## 7. Referential integrity summary

| Relationship | Delete rule | Rationale |
|---|---|---|
| `users` → `auth_sessions` | CASCADE | Sessions have no meaning without the user |
| `users` → `submissions` | RESTRICT | A submission must never be orphaned; deactivate the user instead |
| `users` → `xp_events` | RESTRICT | Ledger integrity is absolute |
| `classes` → `users.class_id` | SET NULL | Deleting a class must not delete its students |
| `graphs` → `graph_target_vocabulary` | CASCADE | The curation has no meaning without the graph |
| `submissions` → `scores` | CASCADE | A score has no meaning without its submission |
| `vocabulary_items` | never deleted | Soft-deleted via `is_active` (§3.4) |

User removal is a **soft delete** (`users.is_active = false`), not a row delete.
Hard-deleting a user would either destroy their submissions and ledger history
or leave dangling references; neither is acceptable for a system whose data is
intended to support research findings.

---

## 8. Migration strategy

Schema changes are managed with **Alembic**, forward-only and versioned. Each
migration is autogenerated from the SQLAlchemy models, then hand-reviewed —
autogeneration reliably detects table and column changes but not `CHECK`
constraint edits or index predicate changes, both of which this schema relies on.

Seed data (vocabulary categories, the 25+ vocabulary items, achievements, badges,
avatars, sample graphs) ships as a separate idempotent seeding command rather
than as migrations, so that reseeding a development database does not require
inventing a new migration revision each time.

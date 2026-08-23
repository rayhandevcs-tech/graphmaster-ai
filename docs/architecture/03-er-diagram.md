# Entity-Relationship Diagram

> **Revision 2.0** — regenerated for the schema in
> [02-database-schema.md](./02-database-schema.md) revision 2.0.

This diagram is the visual companion to the schema document. Entities,
attributes and cardinalities mirror it exactly.

## 1. Full ER diagram

```mermaid
erDiagram
    AVATARS   ||--o{ USERS : "styles"
    CLASSES   ||--o{ USERS : "enrols"
    USERS     ||--o{ CLASSES : "teaches"
    USERS     ||--o{ AUTH_SESSIONS : "holds"
    USERS     ||--o{ GRAPHS : "authors"
    USERS     ||--o{ VOCABULARY_ITEMS : "curates"
    USERS     ||--o{ SUBMISSIONS : "writes"
    USERS     ||--o{ XP_EVENTS : "earns"
    USERS     ||--o{ USER_ACHIEVEMENTS : "unlocks"
    USERS     ||--o{ USER_BADGES : "receives"
    USERS     ||--o{ LEADERBOARD_ENTRIES : "ranked in"
    USERS     ||--o{ TEACHER_REPORTS : "generates"

    VOCABULARY_CATEGORIES ||--o{ VOCABULARY_ITEMS : "groups"
    VOCABULARY_ITEMS      ||--o{ GRAPH_TARGET_VOCABULARY : "targeted by"
    GRAPHS                ||--o{ GRAPH_TARGET_VOCABULARY : "targets"
    GRAPHS                ||--o{ SUBMISSIONS : "answered by"

    SUBMISSIONS ||--|| SCORES : "scored as"
    SUBMISSIONS ||--o{ XP_EVENTS : "awards"
    SUBMISSIONS ||--o| USER_BADGES : "earns"

    ACHIEVEMENTS ||--o{ USER_ACHIEVEMENTS : "unlocked as"
    ACHIEVEMENTS ||--o{ XP_EVENTS : "awards"
    BADGES       ||--o{ USER_BADGES : "granted as"

    CLASSES ||--o{ LEADERBOARD_ENTRIES : "scopes"
    CLASSES ||--o{ ANALYTICS_SNAPSHOTS : "scopes"
    CLASSES ||--o{ TEACHER_REPORTS : "scopes"

    USERS {
        uuid id PK
        citext email UK
        text password_hash
        text full_name
        text role
        text gender
        uuid avatar_id FK
        uuid class_id FK
        bigint total_xp
        integer current_level
        integer current_streak_days
        integer longest_streak_days
        date last_activity_date
        boolean is_active
        timestamptz created_at
    }

    AVATARS {
        uuid id PK
        text code UK
        text name
        text gender
        text image_url
        boolean is_default
        integer unlock_level
    }

    CLASSES {
        uuid id PK
        text name
        text code UK
        uuid teacher_id FK
        boolean is_active
    }

    AUTH_SESSIONS {
        uuid id PK
        uuid user_id FK
        text refresh_token_hash UK
        inet ip_address
        timestamptz expires_at
        timestamptz revoked_at
    }

    GRAPHS {
        uuid id PK
        text title
        text prompt
        text graph_type
        text difficulty
        jsonb chart_data
        text reference_description
        boolean is_published
        uuid created_by FK
    }

    VOCABULARY_CATEGORIES {
        uuid id PK
        text code UK
        text name
        integer display_order
    }

    VOCABULARY_ITEMS {
        uuid id PK
        uuid category_id FK
        text term
        text lemma UK
        boolean is_phrase
        numeric weight
        boolean is_active
        uuid created_by FK
    }

    GRAPH_TARGET_VOCABULARY {
        uuid id PK
        uuid graph_id FK
        uuid vocabulary_item_id FK
        boolean is_required
    }

    SUBMISSIONS {
        uuid id PK
        uuid user_id FK
        uuid graph_id FK
        text input_method
        text answer_text
        text original_image_path
        text ocr_text
        text ocr_provider
        numeric ocr_confidence
        boolean was_ocr_edited
        integer word_count
        text status
        timestamptz submitted_at
        timestamptz scored_at
    }

    SCORES {
        uuid id PK
        uuid submission_id FK "UK"
        numeric vocabulary_score
        numeric writing_score
        numeric final_score
        numeric vocabulary_percentage
        integer detected_count
        integer unique_detected_count
        integer total_target_count
        jsonb detected_terms
        jsonb missing_terms
        jsonb category_breakdown
        text reward_tier
        jsonb feedback
        text engine_version
    }

    XP_EVENTS {
        uuid id PK
        uuid user_id FK
        integer amount
        text reason
        uuid submission_id FK
        uuid achievement_id FK
        timestamptz created_at
    }

    ACHIEVEMENTS {
        uuid id PK
        text code UK
        text title
        text description
        integer xp_reward
        jsonb rule
    }

    USER_ACHIEVEMENTS {
        uuid id PK
        uuid user_id FK
        uuid achievement_id FK
        uuid submission_id FK
        timestamptz unlocked_at
    }

    BADGES {
        uuid id PK
        text code UK
        text name
        text reward_tier UK
    }

    USER_BADGES {
        uuid id PK
        uuid user_id FK
        uuid badge_id FK
        uuid submission_id FK "UK"
        timestamptz awarded_at
    }

    LEADERBOARD_ENTRIES {
        uuid id PK
        text scope
        uuid class_id FK
        date period_start
        date period_end
        uuid user_id FK
        integer rank
        bigint xp
        numeric average_score
        integer achievement_count
    }

    ANALYTICS_SNAPSHOTS {
        uuid id PK
        text scope
        uuid class_id FK
        uuid user_id FK
        date period_start
        jsonb metrics
    }

    TEACHER_REPORTS {
        uuid id PK
        uuid teacher_id FK
        uuid class_id FK
        text report_type
        text format
        text file_path
        text status
    }
```

## 2. Cardinality notes

| Relationship | Cardinality | Rationale |
|---|---|---|
| `AVATARS → USERS` | 1:N | Many students share the same default cartoon avatar; the avatar is reference data, not per-user data. |
| `CLASSES → USERS` | 1:N | A class enrols many students. A student belongs to at most one class in v1.0 — multi-class enrolment would need a join table, deliberately deferred. |
| `USERS → CLASSES` | 1:N | The reverse edge: one teacher owns many classes. Both edges point at `USERS` for different reasons, which is why the diagram shows two lines between them. |
| `GRAPHS → SUBMISSIONS` | 1:N | A graph is answered by many students and re-attempted by the same student (FR-3.7). |
| `GRAPHS ↔ VOCABULARY_ITEMS` | M:N via `GRAPH_TARGET_VOCABULARY` | A graph targets several terms; a term is targeted by several graphs. |
| `SUBMISSIONS → SCORES` | 1:1 | Exactly one score row per scored submission, enforced by `UNIQUE (submission_id)`. |
| `SUBMISSIONS → USER_BADGES` | 1:0..1 | A scored submission yields exactly one tier badge; a draft or failed one yields none. |
| `USERS → XP_EVENTS` | 1:N | Append-only ledger; every award is a new row. |
| `ACHIEVEMENTS → USER_ACHIEVEMENTS` | 1:N | Many students unlock the same achievement, but `UNIQUE (user_id, achievement_id)` caps it at once each (FR-8.8). |
| `BADGES → USER_BADGES` | 1:N | Badges are re-awardable — a student earns Rising Writer on every 60–89% attempt. |
| `CLASSES → LEADERBOARD_ENTRIES` | 1:N | Rows exist only where `scope = 'class'`, enforced by a `CHECK` constraint. |

## 3. Three design decisions worth explaining

### 3.1 Why badges and achievements are separate tables

They look similar enough to merge, but they behave differently:

- An **achievement** is a permanent, one-time milestone. *First Submission* can
  only ever happen once, and `UNIQUE (user_id, achievement_id)` guarantees it.
- A **badge** reflects performance on a single attempt. A student earns *Rising
  Writer* every time they score 60–89%, and earning it does not stop them
  earning *Practice Needed* on the next attempt.

Merging them would force one of the two to carry a meaningless constraint —
either achievements become re-awardable, breaking FR-8.8, or badges become
one-time, so a student's tenth attempt shows no badge at all.

### 3.2 Why the XP ledger is not a counter

A single `users.total_xp` counter would lose the history of *how* XP was earned.
That history is needed for the activity feed, for period-scoped leaderboards
(weekly XP cannot be derived from a lifetime total), for detecting XP farming,
and for retroactively correcting a scoring bug without guessing at the original
values.

Modelling it as an append-only ledger with a maintained cache on `users` gives
both: O(1) profile reads and a fully replayable history. The partial unique
index on `(user_id, created_at::date) WHERE reason = 'streak_bonus'` makes the
once-per-day rule of FR-8.3 a database guarantee rather than a race condition
waiting for two concurrent submissions.

### 3.3 Why `scores` stores denormalised term lists

`detected_terms` and `missing_terms` duplicate information that could, in
principle, be recomputed by re-running the analyser. They are stored anyway
because the vocabulary library is **mutable** — a teacher can deactivate a term
or change a graph's target set at any time. Without the stored lists, reopening
a result from last month would show feedback that no longer matches the score
the student actually received.

# Entity-Relationship Diagram

This diagram is the visual companion to [02-database-schema.md](./02-database-schema.md). All entities, attributes, and cardinalities below mirror that document exactly.

## 1. Full ER Diagram

```mermaid
erDiagram
    USERS ||--o{ AUTH_SESSIONS : "has"
    USERS ||--o{ GRAPH_PROMPTS : "authors (content_admin)"
    USERS ||--o{ SUBMISSIONS : "writes"
    USERS ||--o{ XP_EVENTS : "earns"
    USERS ||--o{ USER_ACHIEVEMENTS : "unlocks"
    USERS ||--o{ LEADERBOARD_SNAPSHOTS : "ranked in"

    GRAPH_PROMPTS ||--o{ SUBMISSIONS : "answered by"
    GRAPH_PROMPTS ||--o{ OCR_EXTRACTIONS : "extracted from"

    SUBMISSIONS ||--o| NLP_ANALYSES : "scored by"
    SUBMISSIONS ||--o{ XP_EVENTS : "may trigger"

    ACHIEVEMENTS ||--o{ USER_ACHIEVEMENTS : "unlocked as"
    ACHIEVEMENTS ||--o{ XP_EVENTS : "may trigger"

    USERS {
        uuid id PK
        citext email UK
        text password_hash
        text display_name
        text role
        integer current_level
        bigint total_xp
        integer current_streak_days
        integer longest_streak_days
        date last_activity_date
        timestamptz created_at
    }

    AUTH_SESSIONS {
        uuid id PK
        uuid user_id FK
        text refresh_token_hash UK
        text user_agent
        inet ip_address
        timestamptz expires_at
        timestamptz revoked_at
    }

    GRAPH_PROMPTS {
        uuid id PK
        text title
        text chart_type
        text difficulty
        text image_url
        text reference_description
        jsonb target_vocabulary
        text_array tags
        boolean is_published
        uuid created_by FK
    }

    SUBMISSIONS {
        uuid id PK
        uuid user_id FK
        uuid graph_prompt_id FK
        text response_text
        integer word_count
        text status
        numeric overall_score
        timestamptz submitted_at
        timestamptz scored_at
    }

    OCR_EXTRACTIONS {
        uuid id PK
        uuid graph_prompt_id FK
        jsonb raw_text_blocks
        jsonb structured_labels
        text engine_version
        text status
    }

    NLP_ANALYSES {
        uuid id PK
        uuid submission_id FK "UK"
        numeric lexical_diversity_score
        numeric academic_vocabulary_score
        jsonb target_vocabulary_hits
        numeric grammar_signal_score
        numeric structure_score
        text feedback_summary
        text engine_version
    }

    XP_EVENTS {
        uuid id PK
        uuid user_id FK
        integer amount
        text reason
        uuid source_submission_id FK
        uuid source_achievement_id FK
        timestamptz created_at
    }

    ACHIEVEMENTS {
        uuid id PK
        text code UK
        text title
        text description
        integer xp_reward
        jsonb unlock_rule
    }

    USER_ACHIEVEMENTS {
        uuid id PK
        uuid user_id FK
        uuid achievement_id FK
        timestamptz unlocked_at
    }

    LEADERBOARD_SNAPSHOTS {
        uuid id PK
        text period
        date period_start
        uuid user_id FK
        integer rank
        bigint xp_in_period
        timestamptz generated_at
    }
```

## 2. Cardinality Notes

| Relationship | Cardinality | Rationale |
|---|---|---|
| `USERS → SUBMISSIONS` | 1:N | A learner submits many attempts over time, across many prompts. |
| `GRAPH_PROMPTS → SUBMISSIONS` | 1:N | A prompt is reused by many learners and re-attempted by the same learner. |
| `GRAPH_PROMPTS → OCR_EXTRACTIONS` | 1:N (practically 1:1 active) | OCR is run per prompt image, not per submission — a prompt's extracted labels are cached and reused across all submissions answering it. A new row is added only when the image changes or OCR is re-run with a newer engine version. |
| `SUBMISSIONS → NLP_ANALYSES` | 1:0..1 | Each submission is analyzed exactly once per scoring pass; `submission_id` is unique, enforcing at most one current analysis row. |
| `USERS → XP_EVENTS` | 1:N | Append-only ledger — every XP-earning action is a new row, never mutated. This makes `total_xp` fully reconstructable by replaying the ledger, which is the source of truth if the denormalized cache on `users` ever drifts. |
| `ACHIEVEMENTS → USER_ACHIEVEMENTS` | 1:N | Many learners unlock the same achievement; `(user_id, achievement_id)` is unique, so an achievement can only be unlocked once per user. |
| `ACHIEVEMENTS → XP_EVENTS` | 1:N (optional) | An achievement unlock optionally produces one XP event; the FK is nullable because most XP events originate from `submission_scored`, not achievements. |
| `USERS → LEADERBOARD_SNAPSHOTS` | 1:N | A user appears once per `(period, period_start)` snapshot; historical snapshots are retained for trend display. |

## 3. Why `xp_events` Is Modeled as a Ledger, Not a Counter

Storing `users.total_xp` as a mutable counter alone would lose the *history* of how XP was earned — needed for streak/activity feeds, anti-abuse auditing, and recomputation if a scoring bug requires retroactive correction. Modeling it as an **append-only ledger** (`xp_events`) with a denormalized cache on `users.total_xp` gives both: fast reads (no `SUM()` on every profile load) and a fully auditable, replayable history. See [09-gamification-architecture.md](./09-gamification-architecture.md) for how the cache is kept consistent with the ledger.

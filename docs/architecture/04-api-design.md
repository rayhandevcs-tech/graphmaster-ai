# API Design

> **Revision 2.0** — realigned to the specification: three roles, OCR on student
> uploads, vocabulary management, teacher reporting, four leaderboard scopes.

## 1. Overview

- **Base path:** `/api/v1`
- **Format:** JSON, except uploads (`multipart/form-data`) and report downloads
- **Auth:** JWT bearer tokens
- **Transport:** HTTPS only in production
- **Interactive docs:** `/docs` (Swagger UI), `/redoc`, schema at `/openapi.json`

## 2. Resource inventory

| Module | Base path | Purpose |
|---|---|---|
| Auth | `/auth` | Registration, login, refresh, logout, password reset |
| Users | `/users` | Profile, statistics, dashboard |
| Avatars | `/avatars` | Avatar catalogue and selection |
| Classes | `/classes` | Cohort management and enrolment |
| Graphs | `/graphs` | Practice content |
| Vocabulary | `/vocabulary` | Categories and teacher-editable terms |
| Submissions | `/submissions` | The practice flow, including OCR and analysis |
| Gamification | `/gamification` | XP, achievements, badges |
| Leaderboard | `/leaderboard` | Four ranking scopes |
| Analytics | `/analytics` | Metrics and charts |
| Reports | `/reports` | Teacher exports |
| Health | `/health` | Liveness and readiness |

Roles in the tables below: **S** student · **T** teacher · **A** admin ·
**—** public.

## 3. Endpoint reference

### 3.1 Auth

| Method | Path | Description | Roles |
|---|---|---|---|
| POST | `/auth/register` | Create an account with name, email, password, gender; assigns the default avatar for that gender | — |
| POST | `/auth/login` | Exchange credentials for an access + refresh token pair | — |
| POST | `/auth/refresh` | Rotate the refresh token and issue a new access token | — |
| POST | `/auth/logout` | Revoke the current refresh token | S T A |
| POST | `/auth/password-reset/request` | Send a reset token to the registered address | — |
| POST | `/auth/password-reset/confirm` | Set a new password using a reset token | — |

`POST /auth/register` request:

```json
{
  "full_name": "Nadia Rahman",
  "email": "nadia@university.edu",
  "password": "••••••••",
  "gender": "female",
  "class_code": "ENG201B"
}
```

`class_code` is optional; when supplied and valid, the student is enrolled
immediately. Response is `201` with the created profile and a token pair.

### 3.2 Users

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/users/me` | Own profile: role, gender, avatar, XP, level, streak | S T A |
| PATCH | `/users/me` | Update name or avatar | S T A |
| GET | `/users/me/dashboard` | Aggregates for FR-10.1 – FR-10.5 | S |
| GET | `/users/me/submissions` | Own submission history, paginated | S |
| GET | `/users/{id}` | Public profile: name, avatar, level, badges | S T A |
| GET | `/users` | List and filter users | A |
| PATCH | `/users/{id}` | Change role, class or active status | A |

`GET /users/me/dashboard` response:

```json
{
  "total_attempts": 47,
  "average_score": 72.4,
  "highest_score": 94.0,
  "total_xp": 1840,
  "current_level": 9,
  "xp_into_level": 40,
  "xp_for_next_level": 450,
  "current_streak_days": 6,
  "longest_streak_days": 11,
  "achievements": [{"code": "first_submission", "title": "First Steps", "unlocked_at": "..."}],
  "badges": {"crown": 3, "flower": 28, "steady": 9, "hammer": 7},
  "recent_activity": [{"submission_id": "...", "graph_title": "...", "final_score": 81.2, "reward_tier": "flower", "submitted_at": "..."}],
  "score_trend": [{"date": "2026-08-01", "average_score": 64.0}]
}
```

### 3.3 Avatars

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/avatars` | Catalogue, filterable by gender; marks which are unlocked for the caller | S T A |
| PUT | `/users/me/avatar` | Select an avatar of the caller's own gender at or below their level | S T A |

### 3.4 Classes

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/classes` | Teachers see their own classes; admins see all | T A |
| POST | `/classes` | Create a class; generates a join code | T A |
| GET | `/classes/{id}` | Class detail with enrolment count | T A |
| PATCH | `/classes/{id}` | Update name, description or active status | T A |
| GET | `/classes/{id}/students` | Roster with per-student summary statistics | T A |
| POST | `/classes/{id}/students` | Enrol a student by email | T A |
| DELETE | `/classes/{id}/students/{user_id}` | Unenrol a student | T A |
| POST | `/classes/join` | Student self-enrols with a join code | S |

Teachers may only act on classes they own; admins are unrestricted (FR-11.6).

### 3.5 Graphs

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/graphs` | List published graphs; filters `graph_type`, `difficulty`, `search` | S T A |
| GET | `/graphs/{id}` | Detail including `chart_data` and the target vocabulary count | S T A |
| GET | `/graphs/random` | One random published graph, optionally filtered — the "Start practice" entry point | S |
| POST | `/graphs` | Create a graph | T A |
| PATCH | `/graphs/{id}` | Update a graph | T A |
| DELETE | `/graphs/{id}` | Delete an unattempted graph; returns `409` if submissions exist | T A |
| POST | `/graphs/{id}/publish` | Publish or unpublish | T A |
| GET | `/graphs/{id}/target-vocabulary` | The curated target set | T A |
| PUT | `/graphs/{id}/target-vocabulary` | Replace the target set with a list of vocabulary item IDs | T A |

Students never receive `reference_description` from `GET /graphs/{id}` before
submitting — it is a model answer, and returning it would let a student copy it.
It appears only in the result payload after scoring. This is enforced by
returning a different response model to students, which has no such field,
rather than by omitting the value at serialisation time.

Three further rules constrain this resource:

- **A graph is created unpublished** and cannot be published until it has at
  least one *required* target term. The vocabulary percentage is
  `detected / required targets`, so publishing an empty target set would put a
  zero in that denominator and make the exercise unscoreable. The same check
  refuses a `PUT .../target-vocabulary` that would empty the required set of an
  already-published graph.
- **Unpublished graphs read as `404` to students**, not `403`, so drafts cannot
  be enumerated. `include_unpublished=true` is honoured for teachers and
  administrators and ignored for students.
- **Editing is open to any teacher; deletion is not.** The practice library is
  shared, so any teacher may improve any graph, but `DELETE` is irreversible
  and is restricted to the graph's author or an administrator.

### 3.6 Vocabulary

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/vocabulary/categories` | The seven categories | S T A |
| GET | `/vocabulary/items` | Terms; filters `category`, `is_active`, `search` | S T A |
| POST | `/vocabulary/items` | Create a term | T A |
| PATCH | `/vocabulary/items/{id}` | Update term, lemma, category or weight | T A |
| DELETE | `/vocabulary/items/{id}` | Deactivate (soft delete — see schema §3.4) | T A |
| POST | `/vocabulary/items/bulk` | Create many terms in one request | T A |

`DELETE` is a soft delete: the row survives so historical scores that reference
the term stay readable, and the lemma stays reserved. Reactivate with
`PATCH {"is_active": true}`.

`POST /vocabulary/items/bulk` **skips** terms whose lemma already exists rather
than failing the whole request, and reports them in `skipped`. A teacher
pasting forty terms where three already exist should not lose the other
thirty-seven.

`is_phrase` is never accepted from the client — it is derived from whether the
term contains whitespace, so the flag cannot disagree with the term. `lemma`
defaults to the lowercased term; supply it explicitly for irregular forms
(`"higher than"` → `"high than"`). Changing a term does **not** re-derive a
lemma that was set by hand, because that would silently stop the term being
detected.

### 3.7 Submissions — the practice flow

| Method | Path | Description | Roles |
|---|---|---|---|
| POST | `/submissions` | Open a submission for a graph, choosing `typed` or `handwriting` | S |
| POST | `/submissions/{id}/upload` | Upload the handwriting image; runs OCR; returns the extracted text | S |
| PATCH | `/submissions/{id}/text` | Set or correct the answer text before analysis (FR-4.7) | S |
| POST | `/submissions/{id}/analyze` | Run the analysis, score, and award gamification | S |
| GET | `/submissions/{id}` | Submission with its score, badge and XP breakdown | S T A |
| GET | `/submissions/{id}/image` | Stream the original uploaded image | S T A |
| GET | `/submissions` | List; students see their own, teachers see their classes' | S T A |
| DELETE | `/submissions/{id}` | Discard an unscored draft | S |

`POST /submissions/{id}/upload` — `multipart/form-data`, field `file`:

```json
{
  "submission_id": "...",
  "status": "extracted",
  "ocr_text": "The graph shows a steady increase in solar output...",
  "ocr_provider": "easyocr",
  "ocr_confidence": 0.8734,
  "warning": null
}
```

When every provider fails, the response is `422` with code `OCR_FAILED`, the
submission stays in `failed`, and the uploaded image is retained (FR-4.9).

`POST /submissions/{id}/analyze` response:

```json
{
  "submission": { "id": "...", "status": "scored", "word_count": 187 },
  "score": {
    "vocabulary_score": 87.50,
    "writing_score": 74.00,
    "final_score": 83.45,
    "vocabulary_percentage": 87.50,
    "detected_count": 14,
    "unique_detected_count": 7,
    "total_target_count": 8,
    "detected_terms": [
      {"term": "increase", "category": "increase", "count": 3},
      {"term": "higher than", "category": "comparison", "count": 1}
    ],
    "missing_terms": [{"term": "fluctuate", "category": "fluctuation"}],
    "category_breakdown": {"increase": {"hit": 2, "target": 2}},
    "reward_tier": "flower",
    "feedback": {
      "headline": "Rising Writer",
      "message": "Strong vocabulary range. You used 7 of 8 target terms.",
      "strengths": ["Good use of increase and comparison language"],
      "improvements": ["Try describing the irregular section using 'fluctuate'"]
    }
  },
  "gamification": {
    "xp_awarded": 50,
    "xp_breakdown": [
      {"reason": "submission", "amount": 20},
      {"reason": "high_score_bonus", "amount": 30}
    ],
    "level_before": 8,
    "level_after": 9,
    "leveled_up": true,
    "badge": {"code": "rising_writer", "name": "Rising Writer"},
    "new_achievements": [{"code": "ten_submissions", "title": "Getting Serious"}],
    "streak_days": 6
  },
  "reference_description": "The line graph illustrates..."
}
```

The endpoint returns scoring **and** gamification in a single payload. The
result screen needs both simultaneously to sequence its animation — splitting
them across two calls would make the reward render before the XP bar knows what
to animate to.

### 3.8 Gamification

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/gamification/xp-history` | Paginated XP ledger for the caller | S T A |
| GET | `/gamification/achievements` | Full catalogue with unlock state and progress | S T A |
| GET | `/gamification/badges` | Badge catalogue with the caller's earned counts | S T A |
| GET | `/gamification/level` | Current level, XP into level, XP to next | S T A |

### 3.9 Leaderboard

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/leaderboard` | Ranked entries; `scope=global\|class\|weekly\|monthly`, optional `class_id`, `limit`, `offset` | S T A |
| GET | `/leaderboard/me` | The caller's rank in a given scope, even when outside the visible page (FR-9.5) | S |

### 3.10 Analytics

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/analytics/vocabulary-usage` | Most and least used terms; `scope=platform\|class`, `class_id`, date range | T A |
| GET | `/analytics/class/{id}` | Average score, tier distribution, engagement | T A |
| GET | `/analytics/trends` | Score and vocabulary trends over time | T A |
| GET | `/analytics/platform` | Platform-wide metrics | A |

### 3.11 Reports

| Method | Path | Description | Roles |
|---|---|---|---|
| POST | `/reports` | Request a report: `report_type`, `format`, `class_id`, filters | T A |
| GET | `/reports` | List the caller's generated reports | T A |
| GET | `/reports/{id}` | Report status | T A |
| GET | `/reports/{id}/download` | Stream the generated file | T A |

### 3.12 Health

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/health/live` | Process is running | — |
| GET | `/health/ready` | Database reachable, OCR providers probed, spaCy model loaded | — |

## 4. Authentication

**Access token** — JWT, HS256, 30-minute lifetime, sent as
`Authorization: Bearer <token>`. Claims:

```json
{ "sub": "<user uuid>", "role": "student", "gender": "female",
  "type": "access", "exp": 1755000000, "iat": 1754998200, "jti": "..." }
```

`role` is embedded so authorisation needs no database round trip on every
request. It is a **cache**, not the authority: a role change invalidates the
user's sessions, forcing a fresh token rather than allowing a stale elevated
claim to persist for up to 30 minutes.

**Refresh token** — opaque 256-bit random string, 30-day lifetime, SHA-256
hashed into `auth_sessions`, delivered as an `HttpOnly` `Secure` `SameSite=Lax`
cookie so client-side JavaScript cannot read it (mitigating XSS token theft).
Rotated on every use: the presented token is revoked and a new one issued in the
same transaction. Presenting an already-revoked token revokes the entire session
family, on the assumption that a replayed token means it was stolen.

## 5. Conventions

### 5.1 Collections

```json
{ "items": [], "page": 1, "page_size": 20, "total": 143, "total_pages": 8 }
```

`page` is 1-indexed; `page_size` defaults to 20 and is capped at 100.

### 5.2 Errors

```json
{
  "error": {
    "code": "SUBMISSION_NOT_FOUND",
    "message": "Submission not found, or you do not have access to it.",
    "details": {}
  }
}
```

| Status | Meaning |
|---|---|
| 400 | Malformed request |
| 401 | Missing, invalid or expired access token |
| 403 | Authenticated but not authorised |
| 404 | Not found |
| 409 | Conflict — duplicate email, deleting an attempted graph |
| 413 | Upload exceeds the size limit |
| 415 | Unsupported upload type |
| 422 | Semantic validation failure, including `OCR_FAILED` |
| 429 | Rate limit exceeded |
| 500 | Unhandled error |

A student requesting another student's submission receives **404, not 403**.
Returning 403 would confirm that the resource exists, which leaks the existence
of other students' work to anyone enumerating IDs.

Selected error codes:

| Code | Status | Meaning |
|---|---|---|
| `EMAIL_ALREADY_REGISTERED` | 409 | Email is taken |
| `INVALID_CREDENTIALS` | 401 | Login failed |
| `TOKEN_EXPIRED` | 401 | Access token expired; refresh |
| `INSUFFICIENT_ROLE` | 403 | Role lacks permission |
| `SUBMISSION_NOT_FOUND` | 404 | Missing or not owned |
| `SUBMISSION_ALREADY_SCORED` | 409 | Re-analysis attempted |
| `SUBMISSION_NOT_READY` | 409 | Analysis requested with no text |
| `OCR_FAILED` | 422 | Every provider failed |
| `UNSUPPORTED_FILE_TYPE` | 415 | Not JPG/JPEG/PNG/WEBP |
| `FILE_TOO_LARGE` | 413 | Over the configured limit |
| `NO_TARGET_VOCABULARY` | 409 | Graph has no target set and no type default |
| `CLASS_CODE_INVALID` | 404 | Unknown or inactive join code |

### 5.3 Rate limits (NFR-2.5, NFR-2.6)

| Group | Limit |
|---|---|
| `/auth/login`, `/auth/register` | 10 per 5 min per IP |
| `/auth/password-reset/*` | 3 per hour per IP |
| `POST /submissions/*/upload` | 30 per hour per user |
| `POST /submissions/*/analyze` | 60 per hour per user |
| All other authenticated endpoints | 300 per 5 min per user |

Exceeded limits return `429` with `Retry-After`.

## 6. Versioning

Versioned by path prefix (`/api/v1`). Additive changes — new optional fields,
new endpoints — ship without a version bump. Breaking changes ship under a new
prefix, with the previous version supported through a documented sunset window.

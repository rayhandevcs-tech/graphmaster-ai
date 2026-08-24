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

### 3.6b OCR

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/ocr/status` | Which recognition engines this server can actually use | S T A |
| POST | `/ocr/extract` | Read handwriting from an uploaded image and return an editable preview | S T A |

`POST /ocr/extract` recognises an image **without binding it to a submission**.
It is the standalone preview surface: it lets a teacher check how well the
configured engine reads their students' handwriting before setting an
assignment, and it is the same service `POST /submissions/{id}/upload` calls.

`GET /ocr/status` exists so a client can hide the handwriting option entirely
on a server with no engine configured, rather than letting a student photograph
a page and only then discover it cannot be read.

Uploads are validated by **signature bytes**, never by filename or the declared
`Content-Type` — both are trivially forged. `413` for an oversized file, `415`
for anything that is not a JPG, PNG or WEBP, and `422` when every engine fails.
The uploaded original is stored *before* recognition is attempted and is
**never deleted on failure**, so a student can retry or switch to typing
without re-photographing the page (FR-4.9).

An empty extraction is **not** an error: a blank or unreadable page is a
legitimate outcome, so it returns `200` with empty text and a `warning`. Low
confidence never blocks either — it sets a `warning` telling the student to
read the preview carefully.

### 3.6c Analysis — the scoring engine's own surface

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/analysis/engine` | The deployed rubric and the language-model state | T A |
| GET | `/analysis/graphs/{id}/targets` | The target set a submission would be scored against | T A |
| POST | `/analysis/graphs/{id}/preview` | Score arbitrary text against a graph, recording nothing | T A |

`GET /analysis/engine`:

```json
{
  "available": true,
  "engine_version": "1.0.0+989d98ad",
  "pipeline": {"model": "en_core_web_sm", "available": true, "version": "3.8.0",
               "pipes": ["tok2vec", "tagger", "parser", "attribute_ruler", "lemmatizer"]},
  "rubric": {
    "vocabulary_weight": 0.70,
    "writing_weight": 0.30,
    "tier_thresholds": {"crown": 90.0, "flower": 60.0, "steady": 50.0, "hammer": 0.0},
    "target_word_count": {"min": 150, "max": 250}
  }
}
```

Clients render the marking criteria from this rather than hardcoding a copy, so
a rubric retuned for a study does not leave the UI describing rules the server
no longer applies. `engine_version` carries a fingerprint of the rubric for the
same reason — see [08-nlp-architecture.md](./08-nlp-architecture.md) §9.10.

`GET /analysis/graphs/{id}/targets` reports `source` as `curated` when a teacher
set the list and `default` when it was derived from the chart type because none
was set (FR-5.6). Only **required** terms form the denominator of the vocabulary
percentage; deactivated terms drop out of both.

`POST /analysis/graphs/{id}/preview` runs the full pipeline and **stores
nothing** — no submission, no score, no XP. Its response is the same body
`POST /submissions/{id}/analyze` returns under `score`, plus `graph_id`.

Detected terms carry half-open character offsets into the submitted text, so
`text[start:end]` is exactly the matched words and the client highlights them
without re-running any matching:

```json
{"term": "increase", "lemma": "increase", "category": "increase",
 "count": 3, "matched_forms": ["increased", "increasing"],
 "positions": [[45, 54], [128, 138]]}
```

**Both endpoints are restricted to teachers and administrators.** This is a
product decision, not a security boundary:

* Open to students, **preview** would let them iterate a draft against the
  marker until it scored 100 and only then submit — turning the vocabulary
  score from a measure of their range into a search problem, and detaching XP
  from the work that earned it.
* **Targets** hands back the exact list the percentage is computed against.
  Given to a student before they write, the task stops being description and
  becomes transcription of a word list. Students still see every term they
  missed *after* scoring, which is where the list teaches something.

Errors: `404` for an unknown graph, `409` (`NO_TARGET_VOCABULARY`) when a graph
has no targets and none could be derived, `422` for an empty or over-long
answer (the limit is 20,000 characters), and `503`
(`ANALYSIS_ENGINE_UNAVAILABLE`) when the language model is not installed on the
server.

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

#### 3.7a Behaviour a client must account for

**Opening is idempotent while a draft is untouched.** `POST /submissions` for a
graph the student already has a *pristine* draft on (no text, no image) returns
that draft rather than creating a second one, so a double-tapped "Start
practice" does not litter the table. A draft with any work in it is never
reused.

**Scoring is exactly once.** The submission row is locked before its status is
read, so two `analyze` calls racing on one submission serialise: one scores it,
the other gets `409 SUBMISSION_ALREADY_SCORED`. This matters beyond tidiness —
without it both callers would run the engine, one would die on the score's
unique constraint, and from Sprint 7 both would award XP for one piece of work.

**Scoring is final.** Afterwards the text is frozen (`PATCH /text` returns 409)
and the attempt cannot be discarded (`DELETE` returns 409), because the score
carries awarded XP and counts towards achievements and the leaderboard.
Re-attempting a graph means opening a **new** submission; nothing is
overwritten, so improvement across attempts stays visible.

**A failed reading is a recoverable state, not a dead end.** When every engine
fails the submission is left in `failed` with the uploaded image retained and
its path recorded. The student can upload a different photograph, or type the
answer into the same attempt with `PATCH /text` — which returns it to `draft`.
`input_method` deliberately stays `handwriting`: the record should show that
handwriting was attempted and recognition did not work, not that the answer was
typed all along.

**A 503 never consumes the attempt.** If the language model is missing, or no
OCR engine is configured, nothing is written — the same request succeeds once
the server is provisioned. Only a failed *reading* marks the submission, because
only that produced an artifact worth recording.

**`GET /submissions/{id}/image` is authenticated, not static.** A browser will
not attach a bearer token to an `<img src>`, so clients fetch the image as a
blob and render the object URL. That inconvenience is the point: serving
handwriting from a guessable static path would let one student read another's
page. Responses carry `Cache-Control: private, no-store`.

**The model answer is released on marking.** `reference_description` is absent
from a submission until it reaches `scored`, and is always present for teachers
and administrators.

**`total_target_count` is frozen at the time of scoring.** A teacher adding a
target term next week does not move any historical percentage.

**Scoring and awarding are one transaction.** The `gamification` block is
populated by the same call that writes the score, and the two commit together —
a student is never shown a score with no XP beside it. `streak_days` is the
streak *after* this submission; `badge` is null only if the badge catalogue is
unseeded, since every score has a tier.

### 3.8 Gamification

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/gamification/xp-history` | Paginated XP ledger for the caller | S T A |
| GET | `/gamification/achievements` | Full catalogue with unlock state and progress | S T A |
| GET | `/gamification/badges` | Badge catalogue with the caller's earned counts | S T A |
| GET | `/gamification/level` | Current level, XP into level, XP to next | S T A |
| POST | `/gamification/adjustments` | Append a signed correction to a student's ledger | A |

#### 3.8a Behaviour a client must account for

**Nothing here awards anything.** XP is granted in exactly one place — while a
submission is being marked — so there is no endpoint a client can call to earn
it. The single exception is the administrative adjustment, which *appends* a
signed entry; the ledger is never edited or deleted, so a correction appears
beside the award it offsets rather than replacing it.

**Each student is offered one crown achievement.** Graph King and Graph Queen
are gender-gated, and the unreachable one is **absent** from
`/gamification/achievements` rather than listed as locked — showing a goal a
student can never meet misrepresents how much of the catalogue is open to them.

**Locked achievements carry progress.** `progress` / `target` /
`progress_percent` are what let a client show "7 / 10" instead of a padlock. An
unlocked achievement always reads as complete even if the statistic behind it
has since fallen: a broken streak does not un-earn Consistency Champion.

**Badges tally, achievements flag.** One badge is attached to every scored
submission according to its tier, so `earned_count` counts up; an achievement
unlocks once and stays unlocked.

**`xp_for_next_level` is a span, not a total.** It is the width of the current
level, which is what an XP bar needs as its maximum. It is `0` at the cap.

### 3.9 Leaderboard

| Method | Path | Description | Roles |
|---|---|---|---|
| GET | `/leaderboard` | Ranked entries; `scope=global\|class\|weekly\|monthly`, optional `class_id`, `page`, `page_size` | S T A |
| GET | `/leaderboard/me` | The caller's rank in a given scope, even when outside the visible page (FR-9.5) | S |
| POST | `/leaderboard/refresh` | Rebuild every scope plus one board per active class | A |

#### 3.9a Behaviour a client must account for

**Rankings are materialised, so a board can be minutes old.** `period.generated_at`
says how old. A read that finds the period stale rebuilds it, which is why a
`GET` here is occasionally slow — and occasionally writes.

**Only students who practised in the period are ranked.** A weekly board listing
every enrolled student on zero buries the few who worked. A student with no
activity gets `entry: null` from `/leaderboard/me`, not an error.

**Teachers and administrators are never ranked**, even if they have scored work
of their own.

**Class boards are not browsable.** A student is pinned to their own class and a
`class_id` they pass is ignored; a teacher must name a class they own, and
naming someone else's returns 403. An unenrolled student asking for
`scope=class` gets 422 explaining they need a class code, not an empty board.

**An entry never carries a reward tier.** Rank, name, avatar, level, XP, average
score, submission count and achievement count only — a hammer count is private
to the student's own results screen (FR-7.6).

**`xp` is period XP, not lifetime.** For `weekly` and `monthly` it is what the
ledger recorded inside the window, which is the reason the ledger exists: a
period total cannot be derived from a lifetime one.

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
| `ANALYSIS_FAILED` | 422 | This answer could not be analysed (empty, or over the length limit) |
| `ANALYSIS_ENGINE_UNAVAILABLE` | 503 | The language model is not installed on this server |
| `UNSUPPORTED_FILE_TYPE` | 415 | Not JPG/JPEG/PNG/WEBP |
| `FILE_TOO_LARGE` | 413 | Over the configured limit |
| `NO_TARGET_VOCABULARY` | 409 | Graph has no target set and no type default |
| `SERVICE_UNAVAILABLE` | 503 | Handwriting upload with no recognition engine configured |
| `CLASS_CODE_INVALID` | 404 | Unknown or inactive join code |

### 5.3 Rate limits (NFR-2.5, NFR-2.6)

| Group | Limit |
|---|---|
| `/auth/login`, `/auth/register` | 10 per 5 min per IP |
| `/auth/password-reset/*` | 3 per hour per IP |
| `POST /submissions/*/upload` | 30 per hour per user |
| `POST /submissions/*/analyze` | 60 per hour per user |
| `POST /analysis/graphs/*/preview` | 60 per hour per user (same bucket — parsing costs the same whether or not the result is persisted) |
| All other authenticated endpoints | 300 per 5 min per user |

Exceeded limits return `429` with `Retry-After`.

## 6. Versioning

Versioned by path prefix (`/api/v1`). Additive changes — new optional fields,
new endpoints — ship without a version bump. Breaking changes ship under a new
prefix, with the previous version supported through a documented sunset window.

# API Design

## 1. Overview

The FastAPI backend exposes a versioned, resource-oriented REST API consumed by the Next.js frontend (see [06-frontend-architecture.md](./06-frontend-architecture.md)) and internally by OCR/NLP workers for result callbacks. All endpoints operate on the entities defined in [02-database-schema.md](./02-database-schema.md).

- **Base path**: `/api/v1`
- **Format**: JSON request/response bodies, `Content-Type: application/json` (except image upload, `multipart/form-data`)
- **Auth**: JWT bearer tokens (see §4)
- **Transport**: HTTPS only

## 2. Resource Inventory

| Resource | Base Path | Description |
|---|---|---|
| Auth | `/api/v1/auth` | Registration, login, token refresh, logout |
| Users | `/api/v1/users` | Profile, stats, streak info |
| Graph Prompts | `/api/v1/prompts` | Browse/manage graph description exercises |
| Submissions | `/api/v1/submissions` | Create and retrieve learner responses |
| OCR | `/api/v1/prompts/{id}/ocr` | Trigger/retrieve OCR extraction for a prompt |
| NLP Analysis | `/api/v1/submissions/{id}/analysis` | Retrieve NLP scoring for a submission |
| Gamification | `/api/v1/gamification/*` | XP, achievements, leaderboard |

## 3. Endpoint Reference

### 3.1 Auth

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Create a new learner account | None |
| POST | `/auth/login` | Exchange credentials for access + refresh token | None |
| POST | `/auth/refresh` | Exchange a valid refresh token for a new access token | Refresh token |
| POST | `/auth/logout` | Revoke the current refresh token (`auth_sessions.revoked_at`) | Access token |

### 3.2 Users

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/users/me` | Current user's profile, level, XP, streak | Access token |
| PATCH | `/users/me` | Update display name / avatar | Access token |
| GET | `/users/{id}` | Public profile (display name, level, achievements) | Access token |

### 3.3 Graph Prompts

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/prompts` | List published prompts; filters: `chart_type`, `difficulty`, `tags` | Access token |
| GET | `/prompts/{id}` | Prompt detail including image URL | Access token |
| POST | `/prompts` | Create a prompt (draft) | `content_admin` |
| PATCH | `/prompts/{id}` | Update prompt fields | `content_admin` |
| POST | `/prompts/{id}/publish` | Flip `is_published` to true | `content_admin` |

### 3.4 OCR

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/prompts/{id}/ocr` | Enqueue OCR extraction job for a prompt's image (idempotent — no-ops if a completed extraction already exists for the current image/engine version) | `content_admin` |
| GET | `/prompts/{id}/ocr` | Retrieve latest `ocr_extractions` row and its status | Access token |

Full pipeline detail in [07-ocr-architecture.md](./07-ocr-architecture.md).

### 3.5 Submissions

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/submissions` | Create a submission for a prompt; enqueues NLP analysis job; returns `202 Accepted` with `status: pending` | Access token |
| GET | `/submissions/{id}` | Retrieve a submission and its current status/score | Access token (owner only) |
| GET | `/submissions` | List current user's submission history; filters: `graph_prompt_id`, `status` | Access token |

### 3.6 NLP Analysis

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/submissions/{id}/analysis` | Retrieve the `nlp_analyses` row (404 until scoring completes) | Access token (owner only) |

Full pipeline detail in [08-nlp-architecture.md](./08-nlp-architecture.md).

### 3.7 Gamification

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/gamification/xp-history` | Paginated `xp_events` for the current user | Access token |
| GET | `/gamification/achievements` | Full achievement catalog with unlock status for current user | Access token |
| GET | `/gamification/leaderboard` | Ranked leaderboard; query params: `period=daily\|weekly\|all_time` | Access token |

Full rules in [09-gamification-architecture.md](./09-gamification-architecture.md).

## 4. Authentication Scheme

- **Access token**: short-lived JWT (15 min), signed HS256/RS256, carries `sub` (user id) and `role`. Sent as `Authorization: Bearer <token>`.
- **Refresh token**: long-lived (30 days), opaque random string, hashed and stored in `auth_sessions`. Sent via `POST /auth/refresh`; rotated on every use (old hash invalidated, new row issued) to limit replay window.
- **Authorization**: role checks (`learner` vs `content_admin`) enforced as a FastAPI dependency at the router level, not scattered in handler bodies — see [05-backend-architecture.md](./05-backend-architecture.md).

## 5. Request/Response Conventions

### 5.1 Envelope

Successful responses return the resource directly (no wrapper envelope) for single-resource endpoints, and a paginated envelope for collections:

```json
{
  "items": [ { "...": "..." } ],
  "page": 1,
  "page_size": 20,
  "total": 143
}
```

### 5.2 Pagination

Collection endpoints accept `page` (1-indexed) and `page_size` (default 20, max 100) query parameters and return the envelope above.

### 5.3 Error Format

All errors follow a consistent shape (aligned with FastAPI's `HTTPException` + a custom exception handler):

```json
{
  "error": {
    "code": "SUBMISSION_NOT_FOUND",
    "message": "Submission 3f2a... was not found or you do not have access to it.",
    "details": {}
  }
}
```

| HTTP Status | Usage |
|---|---|
| 400 | Validation failure (malformed input) |
| 401 | Missing/invalid/expired access token |
| 403 | Authenticated but not authorized (role/ownership check failed) |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate email on register) |
| 422 | Semantic validation failure (Pydantic model errors) |
| 429 | Rate limit exceeded |
| 500 | Unhandled server error |

### 5.4 Async Job Pattern

Endpoints that trigger OCR/NLP work (`POST /submissions`, `POST /prompts/{id}/ocr`) return `202 Accepted` immediately with the created/updated resource in its `pending`/`processing` state. Clients poll the corresponding `GET` endpoint until `status` reaches a terminal value (`scored`, `completed`, or `failed`). This mirrors the async job architecture described in [05-backend-architecture.md](./05-backend-architecture.md) and [01-system-architecture.md](./01-system-architecture.md).

## 6. Versioning

The API is versioned via URL path prefix (`/api/v1`). Breaking changes ship under a new prefix (`/api/v2`); additive, backward-compatible changes (new optional fields, new endpoints) do not require a version bump. Deprecated versions are supported for a documented sunset window to give the frontend time to migrate.

## 7. Rate Limiting

Applied per authenticated user (and per IP for unauthenticated auth endpoints) via a token-bucket limiter backed by Redis:

| Endpoint group | Limit |
|---|---|
| `/auth/login`, `/auth/register` | 10 requests / 5 min / IP |
| `POST /submissions` | 20 requests / hour / user |
| All other authenticated endpoints | 300 requests / 5 min / user |

Rate-limited requests receive `429` with a `Retry-After` header.

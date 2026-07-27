# Developer Landing API

Backend service for a developer's landing-page presentation: a validated
contact form with **AI triage of every message**, email notifications (owner +
user copy), rate limiting, structured file logging, and submission metrics —
built on a clean layered architecture.

> Full request cycle, exactly as required:
> **request → validation → business logic → AI → email → response.**

- **Live API:** _run locally (below) — takes ~1 minute. A hosted URL can be added on Render/Railway using the included Dockerfile._
- **Interactive docs (Swagger UI):** `http://localhost:8000/docs`
- **Landing page (frontend):** `http://localhost:8000/`

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Environment variables](#2-environment-variables)
3. [Tech stack](#3-tech-stack)
4. [Architecture](#4-architecture)
5. [API reference](#5-api-reference)
6. [AI integration](#6-ai-integration)
7. [What was done with AI (and what I fixed by hand)](#7-what-was-done-with-ai)
8. [Data storage](#8-data-storage)
9. [Testing](#9-testing)
10. [Deployment](#10-deployment)

---

## 1. Quick start

Requires **Python 3.9+** (developed and tested on 3.11).

```bash
# 1. Clone and enter the project
cd "developer-landing-api"

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (works out of the box with safe defaults)
cp .env.example .env               # Windows: copy .env.example .env

# 5. Run
python run.py                      # or: uvicorn app.main:app --reload
```

Then open:

| URL | What |
|-----|------|
| <http://localhost:8000/> | Landing page + working contact form |
| <http://localhost:8000/docs> | Swagger UI (try the endpoints live) |
| <http://localhost:8000/api/health> | Service + dependency status |

**It works with zero configuration.** With no API key and no SMTP server, the
service still runs the full pipeline: the AI step uses a deterministic
rule-based **fallback**, and emails run in **console (dry-run) mode** (rendered
to the log instead of sent). Add a key / SMTP credentials to enable the real
thing — nothing else changes.

### With Docker

```bash
cp .env.example .env
docker compose up --build
# → http://localhost:8000
```

---

## 2. Environment variables

All configuration comes from environment variables (or a local `.env`).
See [`.env.example`](.env.example) for the full annotated list.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` / `HOST` | `8000` / `0.0.0.0` | Bind address |
| `CORS_ORIGINS` | `localhost:8000,…` | Comma-separated allowed origins |
| `RATE_LIMIT_MAX_REQUESTS` | `5` | Max submissions per window per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window length |
| `ANTHROPIC_API_KEY` | _(empty)_ | Enables live AI; empty → fallback |
| `AI_MODEL` | `claude-haiku-4-5` | Model used for triage |
| `AI_TIMEOUT_SECONDS` | `12` | Hard timeout before falling back |
| `SMTP_HOST` … `SMTP_PASSWORD` | _(empty)_ | SMTP creds; empty → console mode |
| `OWNER_EMAIL` | `owner@example.com` | Where owner notifications go |
| `LOG_FILE` / `LOG_LEVEL` | `data/logs/app.log` / `INFO` | File logging |
| `DATA_DIR` | `data` | Where logs/metrics/rate-limit live |

Secrets are never hard-coded; `.env` is git-ignored.

---

## 3. Tech stack

**Backend**
- **Language:** Python 3.11
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) — async, first-class
  OpenAPI/Swagger generation, and Pydantic validation built in.
- **Server:** Uvicorn (ASGI)
- **Validation:** Pydantic v2 + `pydantic-settings` (env config) + `email-validator`
- **Email:** `aiosmtplib` (non-blocking SMTP)
- **Dependency mgmt:** `pip` + `requirements.txt`

**AI**
- **Provider:** [Anthropic Claude](https://www.anthropic.com/) via the official
  `anthropic` SDK (async client).
- **Model:** `claude-haiku-4-5` — a small, fast, inexpensive model. Message
  triage (sentiment + classification + a short draft reply) is a lightweight
  task where Haiku is the right engineering trade-off for latency and cost on a
  public contact form. It's a single env var (`AI_MODEL`) to change.
- **Feature:** Anthropic **structured outputs** (JSON-schema-constrained
  response) so the model output is always schema-valid.

**Why FastAPI over Flask/Django?** For an API-first service, FastAPI gives the
most value with the least code: async I/O (the request does AI + two emails +
disk writes — all naturally concurrent-friendly), automatic request validation
from type hints, and Swagger/OpenAPI docs generated for free — all explicit
requirements of this task.

---

## 4. Architecture

Strict **layered architecture** — each layer only talks to the one below it,
so responsibilities are isolated and everything is independently testable.

```
          HTTP request
              │
   ┌──────────▼───────────┐   Controllers (app/api/routes/)
   │  contact / health /  │   Thin: HTTP concerns only — rate-limit gate,
   │  metrics routers     │   delegate, return status code.
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐   Services (app/services/)
   │  ContactService      │   Business logic & orchestration:
   │   ├─ AIService       │   validate→analyse→email→persist→respond.
   │   ├─ EmailService    │
   │   └─ RateLimiter     │
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐   Repositories / Handlers (app/repositories/)
   │  SubmissionLogRepo   │   Persistence: JSONL log, JSON metrics,
   │  MetricsRepo         │   file-based rate-limit state.
   └──────────────────────┘

  Cross-cutting: app/core/ (global error handler + request-logging middleware),
                 app/config.py (settings), app/models/ (schemas / contract),
                 app/dependencies.py (composition root / DI container).
```

### Project structure

```
.
├── app/
│   ├── main.py                 # App factory: middleware, CORS, handlers, routers, static
│   ├── config.py               # Pydantic settings from env (.env)
│   ├── logging_config.py       # Rotating file + console logging
│   ├── dependencies.py         # Composition root — builds & wires singletons
│   ├── core/
│   │   ├── exceptions.py        # Domain errors + global exception handlers
│   │   └── middleware.py        # Per-request logging (id, ip, status, timing)
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response models = validation + OpenAPI contract
│   ├── api/routes/
│   │   ├── contact.py           # POST /api/contact
│   │   ├── health.py            # GET  /api/health
│   │   └── metrics.py           # GET  /api/metrics
│   ├── services/
│   │   ├── contact_service.py   # Orchestrates the full pipeline
│   │   ├── ai_service.py        # Claude integration + graceful fallback
│   │   ├── email_service.py     # Owner + user emails (SMTP / console)
│   │   └── rate_limiter.py      # File-based sliding-window limiter
│   └── repositories/
│       ├── log_repository.py    # Append-only JSONL submission log
│       └── metrics_repository.py# Aggregate counters (atomic JSON)
├── frontend/index.html         # Landing page + contact form (talks to the API)
├── tests/test_api.py           # End-to-end tests (hermetic: fallback AI, console email)
├── data/                       # Runtime: logs, metrics, rate-limit (git-ignored)
├── requirements.txt · Dockerfile · docker-compose.yml
├── postman_collection.json · .env.example · README.md
```

### Design patterns used

- **Layered / clean architecture** — Controllers → Services → Repositories.
- **Dependency Injection / Composition root** — `dependencies.py` builds all
  singletons once and exposes them via FastAPI's `Depends`, so services are
  swappable (the tests inject a fallback-only config with no changes to code).
- **Repository pattern** — storage hidden behind `append()` / `read()` /
  `record_submission()`; swapping JSONL for a database wouldn't touch services.
- **Strategy + graceful degradation** — `AIService` and `EmailService` each
  have a real backend and a fallback path behind one interface.
- **Global error handler** — one place maps exceptions → HTTP status + a uniform
  JSON error envelope.

---

## 5. API reference

Base URL (local): `http://localhost:8000`. All endpoints under `/api`.
Every response carries an `X-Request-ID` header for traceability.

### `POST /api/contact`

Submit the contact form. Runs validation → AI triage → emails → persistence.

**Request body**

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | required, 2–100 chars, sanitised |
| `email` | string | required, valid email |
| `phone` | string \| null | optional, 7–20 digits (`+`, spaces, `()`, `-` allowed) |
| `comment` | string | required, 10–2000 chars, sanitised |

```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "phone": "+1 (555) 123-4567",
    "comment": "I loved your portfolio and would like to discuss a backend project."
  }'
```

**`201 Created`**

```json
{
  "success": true,
  "id": "70289f0672df4bbf",
  "message": "Thank you! Your message has been received.",
  "analysis": {
    "sentiment": "positive",
    "category": "sales",
    "priority": "high",
    "summary": "Ada is interested in discussing a backend project.",
    "suggested_reply": "Hi Ada, thanks for reaching out — I'd be glad to discuss your project...",
    "ai_available": true,
    "model": "claude-haiku-4-5"
  },
  "email": { "owner_notified": true, "user_notified": true, "mode": "console" }
}
```

**`422 Unprocessable Entity`** — validation failed (uniform error envelope):

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "details": [
      { "field": "email", "message": "value is not a valid email address: ..." },
      { "field": "comment", "message": "String should have at least 10 characters" }
    ]
  }
}
```

**`429 Too Many Requests`** — rate limit exceeded (includes `Retry-After` header):

```json
{ "error": { "code": "rate_limited", "message": "Too many requests. Please try again later." } }
```

### `GET /api/health`

```json
{
  "status": "ok",
  "app": "Developer Landing API",
  "version": "1.0.0",
  "uptime_seconds": 16.9,
  "dependencies": { "ai": "fallback", "email": "console" }
}
```
`dependencies.ai` is `live` or `fallback`; `dependencies.email` is `smtp` or `console`.

### `GET /api/metrics`

```json
{
  "total_submissions": 12,
  "ai_success": 10,
  "ai_fallback": 2,
  "emails_sent": 12,
  "emails_failed": 0,
  "by_sentiment": { "positive": 7, "neutral": 3, "negative": 2 },
  "by_category":  { "sales": 5, "hiring": 3, "support": 2, "spam": 2 },
  "by_priority":  { "high": 6, "medium": 4, "low": 2 },
  "first_submission_at": "2026-07-27T13:46:53Z",
  "last_submission_at":  "2026-07-27T18:02:11Z"
}
```

### Error handling & status codes

| Situation | Status | Handled by |
|-----------|--------|-----------|
| Success | `200` / `201` | route |
| Invalid input | `422` | validation handler → structured field list |
| Rate limited | `429` | `RateLimitError` → `Retry-After` header |
| AI unavailable | still `201` | internal fallback (never surfaced as an error) |
| Email send fails | still `201` | captured in `email` status, not raised |
| Unexpected error | `500` | global handler (no stack trace leaked) |

Validation and sanitisation (trimming, control-char stripping, length &
format bounds) happen in the Pydantic schema, so the AI and email layers only
ever see clean data.

---

## 6. AI integration

**What it does:** in a single Claude call, each message is triaged into a
structured result — **sentiment analysis**, **request classification**,
**priority**, a one-line **summary**, and a **draft reply** the owner can send.
The owner's notification email includes this triage; the response returns it to
the frontend, which renders it inline.

**Provider/model:** Anthropic Claude (`claude-haiku-4-5`) via the async
`anthropic` SDK, using **structured outputs** (a JSON schema passed as
`output_config.format`) so the model's response is guaranteed schema-valid — no
brittle free-text parsing.

### Graceful fallback (reliability)

The AI step is wrapped so the endpoint **never fails because of it**:

1. **No API key / AI disabled** → deterministic rule-based analyzer is used.
2. **Timeout** (`AI_TIMEOUT_SECONDS`, default 12s) → fall back.
3. **Any API/network/parse error** → caught and logged → fall back.

The fallback is a keyword-based classifier (sentiment from positive/negative
word sets; category from hiring/sales/spam cues) that returns the *same*
`AIAnalysis` shape with `ai_available: false`. Clients and the metrics layer
handle both paths identically. `GET /api/health` reports which path is active.

### Prompts used

**System prompt:**

> You are the triage assistant for a freelance software developer's contact
> form. For each inbound message you classify sentiment, assign a request
> category and priority, summarise it in one sentence, and draft a short, warm,
> professional reply the developer can send back. Treat obvious spam or
> marketing solicitations as category 'spam' with low priority. Never invent
> facts about the developer; keep the reply generic and courteous.

**User message:** the sanitised `name`, `email`, `phone`, and `comment`.

**Output schema (enforced):** `sentiment` ∈ {positive, neutral, negative},
`category` ∈ {support, sales, hiring, feedback, spam, other}, `priority` ∈
{low, medium, high}, plus `summary` and `suggested_reply` strings. See
[`app/services/ai_service.py`](app/services/ai_service.py).

---

## 7. What was done with AI

This project was built with **Claude (Claude Code)** as a pair-programmer.

**Generated / assisted by AI:**
- Initial scaffolding of the layered structure and boilerplate (routers,
  schemas, repository skeletons).
- First drafts of the fallback keyword classifier and the HTML/CSS of the
  landing page.
- Draft docstrings and this README.

**Reviewed and fixed by hand:**
- **AI SDK correctness** — confirmed the current Anthropic model IDs and the
  `output_config.format` structured-outputs shape against the official SDK
  reference (the model landscape moves fast; guessing here is a common source
  of bugs).
- **Concurrency correctness** — moved all blocking file I/O (`RateLimiter`,
  repositories) off the event loop via `asyncio.to_thread` under an
  `asyncio.Lock`, and made metrics/rate-limit writes atomic (temp-file +
  replace) so a crash mid-write can't corrupt state.
- **Fallback boundaries** — ensured *every* AI failure mode (missing key,
  timeout, API error, malformed output) degrades cleanly, and that email
  failures never fail the request.
- **Validation hardening** — control-character stripping, phone regex, and
  length bounds; flattening Pydantic errors into a client-friendly envelope.

**Verification:** the test suite was run (`6 passed`) and the server was driven
end-to-end (health, a real submission through the fallback pipeline, metrics,
422, and 429 all confirmed) before finishing.

---

## 8. Data storage

No database is required — the filesystem is used (as permitted), each concern
in its own file under `DATA_DIR` (default `data/`):

| Concern | File | Format | Notes |
|---------|------|--------|-------|
| **Request logs** | `data/logs/app.log` | text (rotating) | Every HTTP request: id, IP, method, path, status, duration. Rotates at 5 MB × 5. |
| **Submission history** | `data/submissions.jsonl` | JSON Lines | One record per submission (append-only, crash-safe, greppable). |
| **Statistics** | `data/metrics.json` | JSON | Aggregate counters; atomic read-modify-write under a lock. |
| **Rate limiting** | `data/rate_limit.json` | JSON | `{ip: [timestamps]}` sliding window; stale keys pruned. |

**Logs** — configured centrally in `logging_config.py`: console + a rotating
file handler; a middleware logs one line per request. **Rate limiting** — a
per-IP sliding window (`RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`);
old timestamps are pruned on each check and idle IPs dropped so the file stays
small. **Statistics** — updated transactionally after each submission and
served verbatim by `GET /api/metrics`.

All file access is guarded by an `asyncio.Lock` and executed in a thread pool,
so disk I/O never blocks the event loop. Each repository hides its storage
behind a small interface, so swapping in a real database (a nice "plus") is a
localised change.

---

## 9. Testing

Hermetic end-to-end tests (no network, no API key, no SMTP) exercise the whole
stack through FastAPI's `TestClient` — happy path, validation, rate limiting,
health and metrics:

```bash
pip install -r requirements.txt
pytest -q
# 6 passed
```

---

## 10. Deployment

The service is a standard ASGI app and ships with a `Dockerfile` +
`docker-compose.yml`, so it deploys to any container host.

**Docker (local or any host):**
```bash
docker compose up --build       # → http://localhost:8000
```

**Render / Railway / Fly.io / any PaaS:**
1. Point the platform at this repo (it auto-detects the `Dockerfile`), or use a
   Python buildpack with start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. Set the environment variables from [§2](#2-environment-variables) in the
   dashboard (at minimum `ANTHROPIC_API_KEY` and your SMTP creds for the full
   experience; it also runs fine without them).
3. Deploy. `GET /api/health` is a ready-made health-check endpoint (the
   Dockerfile already wires a container `HEALTHCHECK` to it).

**Expose a local instance quickly (ngrok):**
```bash
python run.py
ngrok http 8000                 # share the https URL
```

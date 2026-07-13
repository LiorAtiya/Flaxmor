# SYSTEM_PROMPT.md

> **⏰ Standing reminder:** This file is updated at every step of the assignment. Every exchange / decision / iteration is recorded in the Work Log below. By the end of the process this file will contain the final System Prompt + an explanation of the design choices (submission requirement).

---

## The System Prompt

_(TBD — will be written during the design/implementation phase)_

## Design Choices

_(TBD — explanation of the prompt structure, edge cases considered, and what was iterated on)_

---

## Work Log

### 2026-07-13 — Step 1: Assignment received and initial analysis

**What happened:** The assignment (`assignment 2.txt`) was received. Claude analyzed it and explained the big picture.

**Key points of the analysis:**

- **Architecture:** `User → Open WebUI → Middleware (FastAPI) → OpenAI GPT`
- **3 services:** Open WebUI 0.6.5 (chat UI), DB (persistence), Middleware (the heart of the task).
- **The core trick:** Open WebUI thinks it's talking to OpenAI, but actually talks to the Middleware, which impersonates the OpenAI API, injects a system prompt into every request, and forwards to the real GPT with streaming.

**Middleware requirements:**
- `POST /v1/chat/completions` — intercept, prepend system prompt to `messages`, forward to OpenAI, return SSE stream.
- `GET /v1/models` — required for Open WebUI to function.
- Structured logs for the full request lifecycle.
- `/health` + `/readiness` endpoints.
- Handle OpenAI upstream failures (timeout, 429, 5xx) — clean error, no crash.
- Unit tests for the core logic.

**The Prompt Engineering task:**
- A system prompt that turns GPT into a structured data extractor: identify text type → extract entities into consistent JSON → confidence scores for uncertain fields.
- Fixed output format always, no exceptions.
- Follow-up question (no new text) → answer normally while referencing the extracted data.

**Deliverables:** README (setup + design decisions), SYSTEM_PROMPT.md (this file), unit tests, config for local run. Deadline: 2 days. Python 3.11+.

**Open questions raised (not yet decided):**
1. Streaming + JSON extraction — how to reconcile structured output with streaming.
2. DB choice — Postgres (production-like) or SQLite (simple).
3. Run mode — everything in docker-compose, or Middleware local + the rest in Docker.

### 2026-07-13 — Step 2: This documentation file created

**What happened:** The user asked to create `SYSTEM_PROMPT.md` with a standing reminder to document every step of the correspondence, including the assignment-breakdown message. The file was created with the structure: prompt (TBD) + design choices (TBD) + ongoing work log.

### 2026-07-13 — Step 3: Design Q&A session and decisions

**What happened:** The user asked clarifying questions about the architecture explanation; every design decision was made jointly, with rationale recorded.

**User questions and the answers:**

1. **"Is Open WebUI a React/Angular framework?"** — Neither. It's SvelteKit frontend + Python backend, but irrelevant to us: we run it as a prebuilt Docker image (`ghcr.io/open-webui/open-webui:0.6.5`) and only configure env vars. Black box.
2. **"`GET /v1/models` — are these the LLM's models? Reflected to the client?"** — Yes. It's the standard OpenAI endpoint listing available models; Open WebUI calls it on startup to populate the model-picker dropdown. What the endpoint returns is exactly what the user sees. Without it — no models to pick, no chat.
3. **"Does business logic live in the middleware or the persistence layer?"** — Middleware, exclusively. The persistence layer (Postgres) belongs to Open WebUI alone (chats, users, settings). The middleware is fully **stateless**: receive → inject → forward → stream. Deliberate design — simple proxy, easy to test, easy to explain.
4. **"Is the JSON schema fixed? Who defines it?"** — We define it, inside the system prompt. **Fixed envelope, flexible inner fields**: `text_type` / `extracted_data` / `uncertain_fields` are always present; the fields inside `extracted_data` vary by text type (receipt → vendor/total/date; job listing → title/salary/requirements). A rigid schema for every possible text type is impossible — fixed envelope is the right compromise.
5. **"Streaming vs JSON — what's the conflict? The response is free text, no?"** — Correct, no real conflict. The response is free text containing a JSON block and streams token-by-token fine. A conflict would exist only if the middleware validated the JSON before returning (requires buffering the full response = no streaming). **Decision: no middleware-side validation; format enforced by the prompt only; pure stream passthrough.**
6. **"How do follow-up questions work?"** — GPT has no memory; Open WebUI resends the full conversation history in `messages` on every request. The previously extracted JSON is in the history as an assistant message. The system prompt (injected identically every time) defines two modes: new pasted text → emit JSON envelope; question about extracted data → answer normally referencing the JSON in history. The middleware does nothing special — the distinction lives entirely in the prompt.
7. **"Three services — separate microservices or an internally-split monolith?"** — Three separate containers in docker-compose: `open-webui` (prebuilt image), `postgres` (prebuilt image), `middleware` (our code, built from Dockerfile). Only one of the three is written by us. Not full "microservices architecture" (no service discovery/message bus) — just 3 processes talking HTTP on the compose network.
8. **"Need agent frameworks (CrewAI / AutoGen / LangGraph / LangChain)?"** — Overkill and the wrong tool. Those are orchestration frameworks (agents, chains, state graphs); the middleware is `prepend one message → forward HTTP → stream back`. Frameworks would break the byte-exact OpenAI SSE contract Open WebUI depends on, hide the streaming we must control, and add magic layers to explain in the interview. **Final stack: FastAPI + httpx + structlog + pytest.**
9. **"What are httpx and structlog?"** — `httpx`: async HTTP client (like `requests` but non-blocking) with first-class response streaming and connection pooling — our pipe to OpenAI. `structlog`: structured (JSON) logging with a `request_id` bound per request, so every log line of a request carries it — satisfies the "structured logs for the full request lifecycle" requirement.

**Decisions locked (with rationale):**

| Decision | Choice | Why |
|---|---|---|
| DB | Postgres 16 (not SQLite) | User chose best practice; production-like; Open WebUI supports `DATABASE_URL` |
| Run mode | Everything in docker-compose | User decision; one command starts all |
| `/v1/models` | Curated static list (`gpt-4o-mini`, `gpt-4o`) | User approved recommendation: full control, no startup dependency on OpenAI, easy to unit-test, dropdown shows only relevant models |
| Streaming | Pure passthrough, no middleware-side JSON validation | Validation requires buffering = kills streaming; prompt enforces format |
| Business logic | All in middleware, stateless | Persistence belongs to Open WebUI; simple proxy is testable and explainable |
| JSON schema | Fixed envelope, flexible inner fields, defined in the system prompt | Rigid per-type schema impossible for arbitrary text |
| Frameworks | None (no LangChain etc.) | Wrong tool for a transparent proxy; keeps every line explainable |
| Stack | FastAPI + httpx + structlog + pytest | Minimal, async, streaming-capable, structured logging |

**Working agreements set by the user:**
1. Document every step, question, decision, and rationale in this work log.
2. Code principles: KISS, DRY, SRP; type hints on every variable/function; best practice throughout.
3. Gated implementation: after each step — stop, wait for the user's review, continue only after approval.
4. Do not forget the explicit middleware requirements: structured logs for the full request lifecycle, health + readiness endpoints, upstream OpenAI failure handling.

**Next up:** Step 1 — middleware skeleton (config, logging, injection, routes, upstream).

### 2026-07-13 — Step 4: Middleware skeleton + secrets + unit tests + code review

**Skeleton built (user reviewed and approved):** `middleware/app/` — config (pydantic-settings), logging_config (structlog JSON + request_id contextvar), system_prompt (placeholder until prompt authoring), injection (pure core function), upstream (transport-error mapping), routes (chat / models / health), main (app factory + lifespan with shared httpx.AsyncClient). Deviation approved by user: upstream timeout → **504** (not 502); 502 reserved for unreachable upstream.

**User Q&A during review:**
- *Secrets?* — Single real secret: `OPENAI_API_KEY`, lives in `.env` (gitignored), injected by docker-compose. `env.example` template created at project root (note: the name `.env.example` is blocked by local tooling permissions, hence `env.example`). Postgres creds also parameterized there. All config fields verified as used.
- *Error handling scope?* — Three layers: transport failures to OpenAI (504/502), OpenAI error responses passed through (401/429/5xx), client errors (invalid JSON → 400). Assignment requires only upstream handling; the rest is minimal hygiene.
- *Logs to DB or file?* — Neither: JSON to stdout (12-factor). Docker collects; `docker compose logs middleware`. DB belongs to Open WebUI only.
- *Logic in routes vs a service layer?* — Business logic already extracted (injection.py, upstream.py); routes hold orchestration only. A service layer at this scale is over-engineering (KISS).
- *Folder organization?* — Flat `app/` + `routes/` is enough for ~7 modules; folders are born when 3+ files share a family.
- *Why pyproject.toml over requirements.txt?* — Modern standard (PEP 621): one file for deps + dev deps + pytest config + metadata; `requires-python = ">=3.11"` enforces the assignment constraint at install time; Docker installs prod deps only.
- *What is `openai_middleware.egg-info`?* — Editable-install metadata from setuptools; added `*.egg-info/` to .gitignore.

**Unit tests written:** 26 tests, all green. Coverage: injection purity/ordering (5), chat route injection + key replacement + JSON/SSE passthrough + params survival + input validation (8), upstream failures 429/500/401-on-stream/timeout/unreachable/error-shape (6), models list + env override (4), health/ready (3). Upstream mocked with respx; app run via TestClient (lifespan included).

**Code review findings (fixed):**
1. Non-list `messages` (e.g. a string) would be splatted into characters by the prepend — now rejected with 400 `invalid_messages`.
2. Upstream non-JSON body (broken proxy / HTML error page) crashed `.json()` — now a clean 502 `upstream_invalid_response` via a shared `_passthrough_json_response` helper (DRY: used by both the non-stream and stream-error paths).
3. Removed unused `pytest-asyncio` dependency (all tests are sync via TestClient).

**Decisions (user):**
- **Model enforcement: NO** — passthrough philosophy kept; the middleware does not validate `model` against `served_models`. The dropdown curates what users see, but any OpenAI-compatible request is forwarded. Known trade-off, accepted.
- **Middleware auth: NONE** — anyone who can reach port 8000 uses the server's key. Accepted as a local-dev-only limitation; to be documented in the README.

**Next up:** Step 3 (plan) — authoring the extraction system prompt + filling this file's TBD sections.

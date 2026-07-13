# Open WebUI + Middleware Stack

A local development environment where every chat message flows through a FastAPI middleware that turns GPT into a **structured data extractor**:

```
User → Open WebUI (:3000) → Middleware (:8000) → OpenAI GPT
                ↕
            Postgres
```

| Service | What it is | Port |
|---|---|---|
| **Open WebUI 0.6.5** | ChatGPT-like chat UI (prebuilt image) | 3000 |
| **Postgres 16** | Open WebUI's persistence (users, chats) | internal only |
| **Middleware** | FastAPI proxy — impersonates the OpenAI API, prepends the extraction system prompt to every chat request, forwards to OpenAI, streams the response back | 8000 |

The trick: Open WebUI is configured with `OPENAI_API_BASE_URL=http://middleware:8000/v1` — it believes it is talking to OpenAI, but every request passes through the middleware, which injects the system prompt defined in [SYSTEM_PROMPT.md](SYSTEM_PROMPT.md).

## Prerequisites

- Docker Desktop (with Compose v2)
- An OpenAI API key **with billing/credit enabled**
- Python 3.11+ (only if you want to run the middleware or its tests outside Docker)

## Quick start

```bash
# 1. Configure the secret
cp env.example .env          # then edit .env and set OPENAI_API_KEY=sk-...

# 2. Start everything
docker compose up -d --build

# 3. Open the UI
#    http://localhost:3000  (no login — auth is disabled for local dev)
```

Compose fails fast with a clear message if `OPENAI_API_KEY` is missing. Open WebUI starts only after Postgres and the middleware pass their healthchecks — first startup takes ~a minute.

## Verify it works end to end

> The curl examples below use bash syntax — on Windows run them in **Git Bash** (bundled with Git for Windows), not PowerShell/cmd.

### 1. Middleware health

```bash
curl http://localhost:8000/health      # {"status":"ok"}
curl http://localhost:8000/ready       # {"status":"ready"}
curl http://localhost:8000/v1/models   # curated list: gpt-4o-mini, gpt-4o
```

### 2. Extraction through the proxy (no UI)

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "SuperPharm branch#42\n13/07/26 14:33\nmilk 3% 2x 6.90 .. 13.80\nTOTL 49.2\nvisa ****1234"}]
  }'
```

Expected: a response whose content is a fenced ```json block with the fixed envelope — `text_type: "receipt"`, `extracted_data`, and the ambiguous date flagged in `uncertain_fields`.

Streaming: add `"stream": true` and `-N` to curl — SSE chunks arrive incrementally, ending with `data: [DONE]`.

### 3. In the UI

1. Open http://localhost:3000, pick `gpt-4o-mini` in the model dropdown.
2. Paste any messy text (receipt, email, job listing…) → the reply is the JSON envelope.
3. Ask a follow-up ("how much was the total?") → a normal answer that references the extracted fields, no new JSON block.

### 4. Structured logs

```bash
docker compose logs middleware | grep request_id
```

Every request emits a JSON lifecycle you can trace by `request_id`:
`request_received → prompt_injected → upstream_request_sent → upstream_response (latency_ms) → request_completed`.
Note `message_count: 1 → 2` between the first two events — the visible proof of injection. Message contents and API keys are never logged.

### 5. Failure handling

Stop your network or set an invalid key: the chat shows a clean OpenAI-shaped error and the middleware stays up. Upstream 4xx/5xx pass through with their original status; timeouts → 504; unreachable upstream → 502.

## Running the unit tests

```bash
cd middleware
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"     # Windows (POSIX: .venv/bin/pip)
.venv/Scripts/python -m pytest -v
```

26 tests cover the core logic with the OpenAI upstream mocked (respx): prompt injection (purity, ordering, existing-system-message), SSE byte-identical passthrough, client-key replacement, parameter passthrough, upstream failures (429/500/401/timeout/unreachable), input validation, models list, health/readiness.

## Configuration

All via `.env` (see [env.example](env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — (required) | Server-side OpenAI key. Client keys are never trusted or forwarded |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Upstream base URL (any OpenAI-compatible API) |
| `SERVED_MODELS` | `["gpt-4o-mini","gpt-4o"]` | Models shown in the Open WebUI dropdown |
| `CONNECT_TIMEOUT_SECONDS` | `10.0` | Upstream connect timeout |
| `READ_TIMEOUT_SECONDS` | `120.0` | Upstream read timeout (long — streams) |
| `LOG_LEVEL` | `INFO` | Middleware log level |
| `POSTGRES_USER/PASSWORD/DB` | `openwebui` / local-dev value | Open WebUI's database |

## Design decisions

| Decision | Choice | Why |
|---|---|---|
| Middleware role | Stateless transparent proxy | Receive → inject → forward → stream. No persistence, no sessions — easy to test, easy to reason about |
| Stack | FastAPI + httpx + structlog only | No LangChain/agent frameworks — they'd break the byte-exact SSE contract Open WebUI depends on and add unexplainable layers. Every line is accountable |
| `/v1/models` | Curated static list | Full control over the dropdown, no startup dependency on OpenAI, trivially testable |
| Streaming | Pure byte passthrough, no middleware-side JSON validation | Validating the extraction output would require buffering the full response — killing streaming. Format is enforced by the prompt |
| Prompt injection position | Our system message always **first**, before any client system message | The assignment requires *prepending*; first position gets the strongest instruction weight |
| Auth to OpenAI | Server-side key only; client `Authorization` dropped | The key never leaves the server side; Open WebUI holds a dummy value |
| DB | Postgres 16 (not SQLite) | Production-like persistence, officially supported by Open WebUI via `DATABASE_URL` |
| Error mapping | 4xx/5xx passthrough; timeout → 504; unreachable → 502; always OpenAI-shaped bodies | The UI always knows how to render the error; no stack traces ever leak |
| Logs | Structured JSON to stdout (12-factor) | `docker compose logs` locally; log shippers in real deployments. Full lifecycle per `request_id` |
| Packaging | `pyproject.toml` (PEP 621) | Single file for deps + dev deps + pytest config; `requires-python = ">=3.11"` enforces the assignment constraint at install time |

The prompt-engineering rationale (envelope design, confidence calibration, edge cases, and 10 documented iterations — 5 design-stage, 5 fixing real failures observed in end-to-end and manual UI testing) is documented in [SYSTEM_PROMPT.md](SYSTEM_PROMPT.md).

## Known limitations (deliberate, local-dev scope)

- **No middleware auth** — anyone who can reach port 8000 uses the server's OpenAI key. Fine on localhost; a real deployment would add an auth layer.
- **No model allow-list enforcement** — the dropdown curates what users see, but a direct API caller may request any OpenAI model. Passthrough philosophy, accepted trade-off.
- **`WEBUI_AUTH=false`** — Open WebUI login is disabled for convenience. Do not expose port 3000 beyond localhost.
- **`language` detection is prompt-mitigated, not guaranteed** — models initially misreported the language of text mentioning foreign places/brands; fixed with a few-shot example in the prompt (6/6 correct at re-test, see SYSTEM_PROMPT.md iteration 9), but as with any LLM-enforced rule, it is probabilistic rather than guaranteed.

## Future improvements

Deliberately out of scope for the assignment, in priority order:

1. **Prompt eval suite** — an automated regression corpus (messy receipt, injection email, multi-document paste, follow-up…) asserting envelope validity, mandatory `uncertain_fields` entries, and injection resistance. Would turn prompt quality from manual testing into CI-able regression, and make prompt-shortening measurable instead of a gamble.
2. **Retry with exponential backoff** on upstream 429/5xx — only for requests that haven't started streaming (a stream, once started, cannot be safely retried).
3. **Model allow-list enforcement** — validate `model` against `SERVED_MODELS`, return an OpenAI-shaped 404; closes the cost exposure noted in known limitations.
4. **Middleware auth** — a static bearer key required from clients; closes the open-port limitation.
5. **Usage metrics in logs** — parse the final SSE chunk's `usage` block into `request_completed` for per-request token cost tracking.
6. **Rate limiting** (per-IP) and **CI** (pytest + docker build on push).

## Project structure

```
├── docker-compose.yml        # 3 services: postgres, middleware, open-webui
├── env.example               # configuration template (cp → .env)
├── SYSTEM_PROMPT.md          # the prompt + design rationale + iterations
├── WORKLOG.md                # development-process log (not a deliverable)
├── README.md
└── middleware/
    ├── Dockerfile            # python:3.11-slim, non-root, prod deps only
    ├── pyproject.toml
    ├── app/
    │   ├── main.py           # app factory, lifespan (shared httpx client), request_id middleware
    │   ├── config.py         # pydantic-settings — all env-driven
    │   ├── logging_config.py # structlog → JSON lines
    │   ├── system_prompt.py  # THE injected prompt (source of truth)
    │   ├── injection.py      # core logic: prepend system prompt (pure function)
    │   ├── upstream.py       # transport-error → clean OpenAI-shaped errors
    │   └── routes/
    │       ├── chat.py       # POST /v1/chat/completions (stream + non-stream)
    │       ├── models.py     # GET /v1/models (curated)
    │       └── health.py     # GET /health, GET /ready
    └── tests/                # 26 unit tests, upstream mocked with respx
```

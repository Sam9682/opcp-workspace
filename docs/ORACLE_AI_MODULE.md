# Oracle AI module

The Oracle is the AI assistant of the workspace (`/oracle` page). It sends a question, plus optional context, to one of several AI providers, stores the exchange in `oracle_queries`, and streams the answer to the UI.

Code: `app/oracle/` (router, service, providers, shared resources), `app/models/oracle.py`, `app/models/ai_provider_config.py`. Frontend: `frontend/src/pages/OraclePage.tsx`, `frontend/src/services/oracleService.ts`.

## Providers

| Id | Class | Backend | Settings | Enabled by default |
|----|-------|---------|----------|--------------------|
| `shai` | `ShaiAIProvider` | OpenAI-compatible chat completions on OVH AI Endpoints | `SHAI_API_KEY` (required), `SHAI_API_URL`, `SHAI_MODEL` | yes, and it cannot be disabled |
| `opcp_companion` | `OpcpCompanionProvider` | RAG: pgvector search + OVH AI Endpoints LLM | `OVH_AI_ENDPOINT`, `OVH_AI_TOKEN`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `LLM_ENDPOINT`, `LLM_TOKEN`, `LLM_MODEL`, `PG_*`, `TABLE_NAME` | no |
| `openai` | `OpenAIProvider` | `https://api.openai.com/v1/chat/completions` | `OPENAI_API_KEY` (required), `OPENAI_MODEL` | no |
| `kiro` | `KiroAIProvider` | Local `kiro-cli chat --no-interactive` subprocess | none (the CLI must be installed and authenticated) | no |

Administrators turn providers on and off on **Admin → Configuration**, which calls `GET/PUT /api/admin/ai-providers`. The flags are stored in `ai_provider_config`. A provider with no row uses its default. See [CONFIGURATION.md](CONFIGURATION.md) for setting defaults.

### Shai: business context

On every query, `ShaiAIProvider` reads `conf/shai_context.md` and prepends it to the prompt. That file holds the OPCP business "skill" and is mounted read-only into the backend container, so you can edit it without rebuilding. If it is missing or empty, the query still runs without it.

`conf/shai_context.md` tells the model to use `docs/opcp_external_docs/` as its reference material. The provider does **not** inject those files into the prompt; only the instruction text that names the folder is sent.

### Encrypted OPCP reference documentation

Every file under `docs/opcp_external_docs/` (subfolders included) is stored **encrypted** in the repository. Each file keeps its name; the content becomes an `OPCP-ENCRYPTED:v1:<salt>` header followed by a Fernet token. The key is derived from a passphrase with PBKDF2-HMAC-SHA256.

The passphrase is `KEY_DECRYPT_INFORMATIONS_OPCP` in `.env`. `.env.example` ships the placeholder `!!!ENTER_THE_KEY_HERE`, which counts as "no key". Code: `app/oracle/opcp_docs.py`, `app/security/opcp_docs_crypto.py`.

| Situation | Behaviour |
|-----------|-----------|
| Key set and correct | At startup the backend decrypts the files **in place**. Already-decrypted files are skipped. |
| No key (empty or placeholder) | Files stay encrypted. Each Shai request gets a notice, after the business context, saying the files in `./docs/opcp_external_docs` are encrypted and do not need to be read. |
| Wrong key | Same as "no key". A warning is logged at startup. |

Before each Shai query the backend checks the folder again. If encrypted files are found and a key is configured, it retries decryption first.

In Docker the folder is **not** bind-mounted. The backend decrypts the copy baked into the image, so plaintext never reaches the host's git working tree. Rebuild the image to ship documentation changes. When running the backend outside Docker with the key set, it decrypts the repository copy itself. Re-encrypt before committing; `tests/test_opcp_docs_encryption.py` fails if a plaintext file is found.

To edit the documentation:

```bash
export KEY_DECRYPT_INFORMATIONS_OPCP='<passphrase>'   # or let the script prompt for it
python scripts/opcp_docs_crypto.py decrypt   # edit the Markdown files
python scripts/opcp_docs_crypto.py encrypt   # before committing
python scripts/opcp_docs_crypto.py status    # lists any plaintext file
```

The script works on the folder recursively and skips files already in the requested state. It never stores the passphrase.

### OPCP Companion (RAG)

For each question:

1. Embed the question with `EMBEDDING_MODEL` (default `Qwen3-Embedding-8B`, 4096 dimensions).
2. Retrieve the 3 closest chunks from `md_embeddings` by cosine distance (pgvector `<=>`).
3. Generate the answer with `LLM_MODEL` through the OpenAI Responses API. The system prompt (in French) tells the model to answer only from the retrieved context.
4. Return the answer with `sources` (`title`, `file_path`, `similarity`), which the UI displays under the answer.

`LLM_ENDPOINT`/`LLM_TOKEN` fall back to `OVH_AI_ENDPOINT`/`OVH_AI_TOKEN` when empty. Set `LLM_MODEL` explicitly: its built-in default is an embedding model name. `PG_*` values left at their defaults are derived from `DATABASE_URL`.

The `vector` extension and the `md_embeddings` table are created on first use (they are not managed by Alembic).

#### Ingesting documents

```bash
# Docker Compose (one-off job)
docker compose --profile ingest run --rm ingest

# Local
python -m scripts.ingest_embeddings
```

`scripts/ingest_embeddings.py` requires `OVH_AI_ENDPOINT` and `OVH_AI_TOKEN`. It indexes:

- every `*.md` file **directly** under `docs/` (no recursion), and
- every `*.pdf` file **directly** under `docs/to_publish/` (subfolders are not scanned).

Each file is split into 1000-character chunks with a 100-character overlap and embedded. Its previous rows (matched by `file_path`) are replaced, so re-running is safe. Rows for files that no longer exist are **not** removed; delete them manually if needed (`DELETE FROM md_embeddings WHERE file_path = '...'`). The script exits with status 1 if any file fails.

### Kiro CLI

The backend Dockerfile installs Kiro CLI (`curl -fsSL https://cli.kiro.dev/install | bash`). The container has no browser, so authenticate it once with the device flow:

```bash
docker exec -it <backend-container> kiro-cli login --use-device-flow
```

The login is lost when the container is recreated. Calls time out after one hour.

## API

Prefix `/api/oracle`.

| Method | Path | Access | Notes |
|--------|------|--------|-------|
| POST | `/ask` | anonymous or logged in, 10/min | Returns the full answer |
| POST | `/ask/stream` | anonymous or logged in, 10/min | Server-sent events (used by the UI) |
| GET | `/history?limit=50` | logged in | Caller's own queries |
| GET | `/history/all?limit=100` | administrators | All queries |
| POST | `/analyze/forum` | logged in, 5/hour | AI analysis of all forum content (returns JSON) |
| GET | `/providers` | public | Providers with name, model and `enabled` flag |

Request body for `/ask` and `/ask/stream`:

```json
{
  "question": "How do I install OPCP?",   // 1–5000 chars
  "context": "optional, ≤ 10000 chars",
  "ai_provider": "shai",                   // shai | opcp_companion | openai | kiro
  "temperature": 0.7,                      // 0–2
  "max_tokens": 2000                       // 100–8000
}
```

A disabled provider returns `400`.

`/ask/stream` emits `start` `{provider}`, then `token` `{content, index}` events, then `done` `{id, provider, model, processing_time, tokens_used, sources}`, or `error` `{message}`. The answer is fully generated first and then streamed word by word, so time-to-first-token equals the full generation time. The response sets `X-Accel-Buffering: no`, and nginx has a 600 s proxy timeout.

`/analyze/forum` accepts `analysis_type` (`forum_summary`, `event_prediction`, `user_sentiment`, `custom`) and `ai_provider` (default `kiro`). It does not check whether the provider is enabled.

## Other uses

The [document adapter](DOCUMENTS.md#document-adapter) uses the same providers (`get_ai_provider`). Its calls are not recorded in the Oracle history.

## Troubleshooting

- **"SHAI_API_KEY not configured"**: set `SHAI_API_KEY` in `.env` and restart the backend.
- **Startup warning "OPCP reference documentation is encrypted…"**: set `KEY_DECRYPT_INFORMATIONS_OPCP` in `.env` and restart. If it says some files "could not be decrypted", the key is wrong.
- **`opcp_companion` returns no or irrelevant sources**: run the ingestion job and check `SELECT count(*) FROM md_embeddings;`.
- **Startup warning "Could not warm up Oracle resources"**: this is not fatal. The clients are created lazily on the first query. Check `OVH_AI_*`/`LLM_*` and the database credentials.
- **`kiro-cli: not found` or authentication errors**: rebuild the backend image, then log in as shown above.

# api/ instructions

FastAPI backend. See root `AGENTS.md` first — this file only adds backend-specific notes.

## Layout

- `app/main.py` — app + router wiring + CORS.
- `app/routers/` — HTTP layer only (request/response schemas, persistence calls). Business
  logic belongs in `app/services/`, not here.
- `app/services/search/pipeline.py` — the 6-stage pipeline. `assemble_search()` holds the
  actual fusion/rerank logic and is pure (no DB/Cohere calls) so it's unit-testable; `run_search()`
  is the thin DB/Cohere-calling wrapper around it.
- `app/services/cohere_client.py` — the only place that calls the Cohere API. Every function
  except `embed_texts` (used by offline ingestion only) must catch its own errors and return a
  "skip this stage" value (`None`/`[]`), never raise into the request path.
- `app/db/scoping.py` — the only sanctioned way to query `chunks`/`highlights`; always pass
  `admission_year`. Don't write a raw `select(Chunk)` elsewhere.
- `app/scripts/ingest.py` / `reembed.py` — CLIs run locally (`mise run ingest` / `reembed`)
  against the Supabase DB, not part of the deployed Render service's request path.

## Constraints

- No `torch` / `sentence-transformers` / local CrossEncoder — Stage 5 reranking is the Cohere
  Rerank API (Render's free tier can't hold a local model in memory). Don't reintroduce them.
- Popular-highlight and other public read endpoints must never return a `device_id`. Admin
  endpoints may return query text/category but never `device_id` either — see root AGENTS.md.
- Settings come from `app/config.py::get_settings()` (env vars > repo-root `.env`, see its
  `env_file` comment). Don't read `os.environ` directly elsewhere.

## Tests

```
.venv/bin/pytest -q
```

Tests never hit a real Postgres/pgvector or the real Cohere API — DB access is faked with
`tests/conftest.py::FakeSession` (or a `MagicMock` for raw `db.execute()` calls) and Cohere
calls are monkeypatched or injected via a callable parameter (see
`rerank_candidates(..., rerank_fn=...)`). Keep new DB/Cohere-touching code thin enough to test
this way, and put the actual logic in a pure function next to it.

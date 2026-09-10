# Repository instructions

## Purpose

This is a Japanese university course-guide reading system and a data-engineering teaching
artifact. Preserve the visible Stage 1–6 pipeline: literal search, rule-based terminology
expansion, LLM query expansion, semantic retrieval, reranking, and grounded answer generation.

## Deployment profile (concept-verification phase)

This project currently targets a **cloud-only, entirely free-tier** deployment — there is no
Docker, no Ollama, and no local Postgres in this profile:

- Frontend: Vercel (Next.js)
- Backend: Render free Web Service (FastAPI)
- Database: Supabase free tier (PostgreSQL + pgvector)
- Generative AI / embeddings / reranking: Cohere API (free trial key) — **Cohere is the sole
  AI provider**, not an optional comparison path.

Do not reintroduce Docker Compose, Ollama, or a local in-process CrossEncoder
(sentence-transformers/torch) without explicit instruction — they don't fit the free-tier
memory/runtime budget this phase targets. If local/self-hosted model support is wanted later,
add it behind a provider abstraction rather than replacing the Cohere path.

## Working rules

- Use `mise` tasks as the public command interface for local development.
- Keep WebMCP out of scope unless explicitly requested.
- Preserve strict admission-year/document-ID separation in searches, highlights, and aggregates.
- Never expose anonymous device IDs, full questions, or answers through popular-highlight
  endpoints. Admin endpoints may show search traces/low-rated questions (for teacher review) but
  must never expose anonymous device IDs, in the UI or in CSV export.
- Do not commit `.env`, API keys, or generated caches.
- Treat PDFs under `handbook/` as immutable source data.
- Cohere calls (`api/app/services/cohere_client.py`) must have timeouts and fail gracefully —
  a Cohere error or rate limit must fall back to the Stage 1-2 (non-AI) result, never a 500.
- Run the smallest relevant tests before handoff.

## Runtime architecture

- Next.js calls FastAPI only.
- FastAPI owns search; Stage 5 reranking calls the Cohere Rerank API (no in-process model).
- Cohere supplies chat, embeddings, and reranking over HTTPS.
- Supabase PostgreSQL/pgvector persists application data and document embeddings.
- PDF ingestion and embedding generation (`mise run ingest` / `mise run reembed`) are run
  locally by a developer against the Supabase DB — the deployed Render API only serves
  search/answer/highlight/evaluation requests, it does not re-ingest PDFs at runtime.

## Verification

Run `mise run test` for a full check. For backend-only work use `.venv/bin/pytest -q api`; for
frontend work use `cd web && npm test -- --run` and `npm run build`. Real Cohere/Supabase
connectivity cannot be verified in a sandbox without network egress to those services — mock
them in tests and note when a change needs manual verification against the deployed app.

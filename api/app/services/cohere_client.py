"""Thin wrapper around the Cohere API (chat / embed / rerank).

Cohere is the sole AI provider in this cloud/free-tier deployment profile (see AGENTS.md).
Free trial keys are rate-limited, so every AI-driven stage (3, 4's query embedding, 5, 6) must
degrade gracefully: on any failure these functions log a warning and return a value the caller
can treat as "skip this stage", so the pipeline still returns the Stage 1-2 result instead of
a 500. `embed_texts` (used only by the offline ingestion script) is the one exception — a
failure there should stop ingestion, not be silently swallowed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cohere

from app.config import get_settings

logger = logging.getLogger(__name__)


class CohereUnavailableError(Exception):
    """Raised when the Cohere API key is not configured."""


@dataclass
class RerankResult:
    index: int
    relevance_score: float


_client: cohere.ClientV2 | None = None


def _get_client() -> cohere.ClientV2:
    global _client
    settings = get_settings()
    if not settings.cohere_enabled:
        raise CohereUnavailableError("COHERE_API_KEY is not configured")
    if _client is None:
        _client = cohere.ClientV2(api_key=settings.cohere_api_key, timeout=settings.cohere_timeout_seconds)
    return _client


def _extract_text(response) -> str:
    content = getattr(response.message, "content", None) or []
    parts = [getattr(block, "text", "") for block in content]
    return "\n".join(p for p in parts if p)


def expand_query(query: str) -> list[str]:
    """Stage 3: ask Cohere Chat for extra search terms. Returns [] on any failure."""
    settings = get_settings()
    try:
        client = _get_client()
        response = client.chat(
            model=settings.cohere_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは大学の履修要覧検索アシスタントです。学生の質問から、"
                        "履修要覧を全文検索する際に有効な追加キーワードを日本語で最大5個、"
                        "1行1語で出力してください。説明や記号、番号付けは不要です。"
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.3,
        )
        text = _extract_text(response)
        terms = [line.strip(" 　・-*") for line in text.splitlines() if line.strip()]
        return terms[:5]
    except Exception:
        logger.warning("cohere expand_query failed; continuing without stage3 terms", exc_info=True)
        return []


def embed_texts(texts: list[str], input_type: str) -> list[list[float]]:
    """Raw embedding call. input_type is 'search_document' (ingestion) or 'search_query'.

    Does not catch exceptions: callers doing offline ingestion should fail loudly rather than
    silently skip embedding a chunk.
    """
    settings = get_settings()
    client = _get_client()
    response = client.embed(
        model=settings.cohere_embed_model,
        texts=texts,
        input_type=input_type,
        embedding_types=["float"],
    )
    return response.embeddings.float_ or []


def embed_query(query: str) -> list[float] | None:
    """Stage 4 query embedding. Returns None on failure so semantic search is skipped."""
    try:
        vectors = embed_texts([query], input_type="search_query")
        return vectors[0] if vectors else None
    except Exception:
        logger.warning("cohere embed_query failed; skipping semantic search", exc_info=True)
        return None


def rerank(query: str, documents: list[str], top_n: int | None = None) -> list[RerankResult] | None:
    """Stage 5. Returns None on failure so the caller can keep the pre-rerank order."""
    if not documents:
        return []
    settings = get_settings()
    try:
        client = _get_client()
        response = client.rerank(
            model=settings.cohere_rerank_model,
            query=query,
            documents=documents,
            top_n=top_n or len(documents),
        )
        return [RerankResult(index=r.index, relevance_score=r.relevance_score) for r in response.results]
    except Exception:
        logger.warning("cohere rerank failed; keeping pre-rerank order", exc_info=True)
        return None


def generate_answer(query: str, evidence: list[dict]) -> str | None:
    """Stage 6: grounded answer restricted to `evidence` ([{"id","text","page"}, ...]).

    Returns None on failure so the UI can show search results without an AI answer.
    """
    settings = get_settings()
    try:
        client = _get_client()
        context = "\n\n".join(f"[{i + 1}] (p.{e['page']}) {e['text']}" for i, e in enumerate(evidence))
        response = client.chat(
            model=settings.cohere_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは大学の履修要覧アシスタントです。以下の根拠(抜粋)に書かれている"
                        "内容のみを使って、日本語で質問に答えてください。根拠に書かれていないこと"
                        "は推測せず、「手引きの提示範囲には記載がありません」と答えてください。"
                        "回答文の該当箇所には対応する[番号]を付けて出典を明示してください。"
                    ),
                },
                {"role": "user", "content": f"根拠:\n{context}\n\n質問: {query}"},
            ],
            temperature=0.2,
        )
        return _extract_text(response)
    except Exception:
        logger.warning("cohere generate_answer failed", exc_info=True)
        return None

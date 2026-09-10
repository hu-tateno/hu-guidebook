"""The 6-stage search pipeline.

Stage 1 (literal) and Stage 2 (lexicon expansion) are pure-ish functions over already-fetched
chunks, so they can be unit tested without a database or the Cohere API. Stages 3-6 (Cohere
query expansion, embedding fusion, rerank, grounded answer) are layered on in
app/services/search/pipeline.py's run_search() and call app/services/cohere_client.py, which
degrades to "skip this stage" on any failure — see that module's docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.db.scoping import scoped_chunk_query
from app.services import cohere_client
from app.services.lexicon import expand_terms


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    document_id: int
    admission_year: int
    page_number: int
    heading_path: str | None
    text: str
    bbox: list


@dataclass
class ScoredChunk:
    chunk: ChunkRecord
    score: float
    matched_terms: list[str] = field(default_factory=list)


@dataclass
class StageTrace:
    stage: int
    label: str
    query_terms: list[str]
    result_count: int
    top_chunk_ids: list[int]


def chunk_to_record(chunk: Chunk) -> ChunkRecord:
    return ChunkRecord(
        id=chunk.id,
        document_id=chunk.document_id,
        admission_year=chunk.admission_year,
        page_number=chunk.page_number,
        heading_path=chunk.heading_path,
        text=chunk.text,
        bbox=chunk.bbox,
    )


def fetch_scoped_chunks(db: Session, admission_year: int, document_id: int | None = None) -> list[ChunkRecord]:
    rows = db.execute(scoped_chunk_query(admission_year, document_id)).scalars().all()
    return [chunk_to_record(r) for r in rows]


def literal_search(chunks: list[ChunkRecord], terms: list[str], limit: int = 20) -> list[ScoredChunk]:
    """Stage 1 (terms=[query]) and the literal-search half of Stage 2/3 (terms=query+expansions).

    Score = total case-insensitive substring occurrence count across all terms; only chunks
    matching at least one term are returned, ranked by score descending.
    """
    clean_terms = [t for t in terms if t and t.strip()]
    scored: list[ScoredChunk] = []
    for chunk in chunks:
        haystack = chunk.text.lower()
        matched = [t for t in clean_terms if t.lower() in haystack]
        if not matched:
            continue
        score = sum(haystack.count(t.lower()) for t in matched)
        scored.append(ScoredChunk(chunk=chunk, score=float(score), matched_terms=matched))
    scored.sort(key=lambda sc: sc.score, reverse=True)
    return scored[:limit]


def lexicon_expand(query: str) -> list[str]:
    """Stage 2: institutional terms pulled in from data/search_lexicon.yaml."""
    return expand_terms(query)


def make_trace(stage: int, label: str, terms: list[str], results: list[ScoredChunk]) -> StageTrace:
    return StageTrace(
        stage=stage,
        label=label,
        query_terms=terms,
        result_count=len(results),
        top_chunk_ids=[sc.chunk.id for sc in results[:10]],
    )


def reciprocal_rank_fusion(result_lists: list[list[ScoredChunk]], limit: int = 20, k: int = 60) -> list[ScoredChunk]:
    """Stage 4: merge the literal-search and semantic-search candidate lists.

    Standard reciprocal-rank fusion: a chunk's fused score is the sum, over every result list
    it appears in, of 1/(k + rank_in_that_list + 1). This needs no score normalization between
    the very different literal-match-count and cosine-distance scales.
    """
    scores: dict[int, float] = {}
    records: dict[int, ChunkRecord] = {}
    terms: dict[int, set[str]] = {}
    for results in result_lists:
        for rank, sc in enumerate(results):
            scores[sc.chunk.id] = scores.get(sc.chunk.id, 0.0) + 1.0 / (k + rank + 1)
            records[sc.chunk.id] = sc.chunk
            terms.setdefault(sc.chunk.id, set()).update(sc.matched_terms)
    fused = [
        ScoredChunk(chunk=records[cid], score=score, matched_terms=sorted(terms[cid]))
        for cid, score in scores.items()
    ]
    fused.sort(key=lambda sc: sc.score, reverse=True)
    return fused[:limit]


RerankFn = Callable[[str, list[str], int | None], list[cohere_client.RerankResult] | None]


def rerank_candidates(
    query: str,
    candidates: list[ScoredChunk],
    top_k: int = 8,
    rerank_fn: RerankFn = cohere_client.rerank,
) -> list[ScoredChunk]:
    """Stage 5. Falls back to the pre-rerank (fused) order if the Cohere Rerank call fails."""
    if not candidates:
        return []
    documents = [sc.chunk.text for sc in candidates]
    results = rerank_fn(query, documents, min(top_k, len(candidates)))
    if results is None:
        return candidates[:top_k]
    reranked = []
    for r in results:
        sc = candidates[r.index]
        reranked.append(ScoredChunk(chunk=sc.chunk, score=r.relevance_score, matched_terms=sc.matched_terms))
    return reranked


def assemble_search(
    chunks: list[ChunkRecord],
    query: str,
    llm_terms: list[str],
    semantic_results: list[ScoredChunk],
    top_k: int = 8,
    rerank_fn: RerankFn = cohere_client.rerank,
) -> tuple[list[StageTrace], list[ScoredChunk]]:
    """Stages 1-5, pure: takes already-computed Stage 3 LLM terms and Stage 4 semantic
    candidates (both require the DB/Cohere) and returns the full stage trace plus the
    final reranked list. This is the part of the pipeline covered by unit tests.
    """
    stages: list[StageTrace] = []

    stage1_terms = [query]
    stage1_results = literal_search(chunks, stage1_terms)
    stages.append(make_trace(1, "literal", stage1_terms, stage1_results))

    lexicon_terms = lexicon_expand(query)
    stage2_terms = stage1_terms + lexicon_terms
    stage2_results = literal_search(chunks, stage2_terms)
    stages.append(make_trace(2, "lexicon_expansion", stage2_terms, stage2_results))

    stage3_terms = stage2_terms + llm_terms
    stage3_results = literal_search(chunks, stage3_terms)
    stages.append(make_trace(3, "llm_expansion", stage3_terms, stage3_results))

    fused = reciprocal_rank_fusion([stage3_results, semantic_results])
    stages.append(make_trace(4, "hybrid", stage3_terms, fused))

    reranked = rerank_candidates(query, fused, top_k=top_k, rerank_fn=rerank_fn)
    stages.append(make_trace(5, "rerank", stage3_terms, reranked))

    return stages, reranked


def semantic_search(
    db: Session, admission_year: int, document_id: int | None, query: str, limit: int = 20
) -> list[ScoredChunk]:
    """Stage 4's embedding half: pgvector cosine-distance search, scoped like every other
    chunk read. Returns [] if the Cohere embed call fails or no chunk has an embedding yet."""
    query_vector = cohere_client.embed_query(query)
    if query_vector is None:
        return []
    stmt = (
        scoped_chunk_query(admission_year, document_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    # Rank-based score (not the raw distance) since this feeds reciprocal_rank_fusion, which
    # only uses relative rank across lists.
    return [
        ScoredChunk(chunk=chunk_to_record(row), score=float(limit - rank), matched_terms=["(semantic)"])
        for rank, row in enumerate(rows)
    ]


@dataclass
class SearchRunResult:
    query: str
    admission_year: int
    document_id: int | None
    stages: list[StageTrace]
    final_results: list[ScoredChunk]
    answer: str | None


def run_search(
    db: Session,
    admission_year: int,
    document_id: int | None,
    query: str,
    top_k: int = 8,
    want_answer: bool = True,
) -> SearchRunResult:
    """The full 6-stage pipeline. Thin DB/Cohere-calling orchestration around
    assemble_search(), which holds the actual fusion/rerank logic and is what's unit tested."""
    chunks = fetch_scoped_chunks(db, admission_year, document_id)
    llm_terms = cohere_client.expand_query(query)
    semantic_results = semantic_search(db, admission_year, document_id, query)

    stages, reranked = assemble_search(chunks, query, llm_terms, semantic_results, top_k=top_k)

    answer = None
    if want_answer and reranked:
        evidence = [{"id": sc.chunk.id, "text": sc.chunk.text, "page": sc.chunk.page_number} for sc in reranked[:5]]
        answer = cohere_client.generate_answer(query, evidence)
    stages.append(make_trace(6, "answer", [], reranked[:5] if answer else []))

    return SearchRunResult(
        query=query,
        admission_year=admission_year,
        document_id=document_id,
        stages=stages,
        final_results=reranked,
        answer=answer,
    )

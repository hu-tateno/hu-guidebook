from app.services.cohere_client import RerankResult
from app.services.search.pipeline import (
    ChunkRecord,
    ScoredChunk,
    assemble_search,
    reciprocal_rank_fusion,
    rerank_candidates,
)


def _chunk(id_, text="text"):
    return ChunkRecord(
        id=id_, document_id=1, admission_year=2024, page_number=1, heading_path=None, text=text, bbox=[]
    )


def _sc(id_, score, terms=None):
    return ScoredChunk(chunk=_chunk(id_), score=score, matched_terms=terms or [])


def test_reciprocal_rank_fusion_favors_chunks_in_both_lists():
    literal = [_sc(1, 5.0), _sc(2, 3.0), _sc(3, 1.0)]
    semantic = [_sc(2, 10.0), _sc(4, 8.0)]
    fused = reciprocal_rank_fusion([literal, semantic])
    # chunk 2 appears in both lists (rank 1 in each) so it should come out on top
    assert fused[0].chunk.id == 2


def test_reciprocal_rank_fusion_merges_matched_terms():
    literal = [_sc(1, 5.0, ["休学"])]
    semantic = [_sc(1, 9.0, ["(semantic)"])]
    fused = reciprocal_rank_fusion([literal, semantic])
    assert fused[0].chunk.id == 1
    assert set(fused[0].matched_terms) == {"休学", "(semantic)"}


def test_reciprocal_rank_fusion_respects_limit():
    literal = [_sc(i, float(i)) for i in range(30)]
    fused = reciprocal_rank_fusion([literal], limit=5)
    assert len(fused) == 5


def test_reciprocal_rank_fusion_empty_lists():
    assert reciprocal_rank_fusion([[], []]) == []


def test_rerank_candidates_reorders_by_cohere_result():
    candidates = [_sc(1, 1.0, ["a"]), _sc(2, 1.0, ["b"]), _sc(3, 1.0, ["c"])]

    def fake_rerank(query, documents, top_n):
        # pretend chunk at index 2 (id=3) is actually most relevant
        return [
            RerankResult(index=2, relevance_score=0.9),
            RerankResult(index=0, relevance_score=0.4),
        ]

    result = rerank_candidates("q", candidates, top_k=5, rerank_fn=fake_rerank)
    assert [sc.chunk.id for sc in result] == [3, 1]
    assert result[0].score == 0.9
    assert result[0].matched_terms == ["c"]


def test_rerank_candidates_falls_back_to_input_order_on_failure():
    candidates = [_sc(1, 1.0), _sc(2, 1.0), _sc(3, 1.0)]

    def failing_rerank(query, documents, top_n):
        return None  # cohere_client.rerank returns None on any error

    result = rerank_candidates("q", candidates, top_k=2, rerank_fn=failing_rerank)
    assert [sc.chunk.id for sc in result] == [1, 2]


def test_rerank_candidates_empty_input():
    assert rerank_candidates("q", [], rerank_fn=lambda *a: None) == []


def test_assemble_search_produces_six_minus_one_stages_and_uses_injected_rerank():
    chunks = [
        _chunk(1, "休学を希望する場合は休学願を提出してください。"),
        _chunk(2, "卒業要件は124単位以上の修得です。"),
    ]
    semantic_results = [_sc(2, 5.0, ["(semantic)"])]

    def fake_rerank(query, documents, top_n):
        return [RerankResult(index=i, relevance_score=1.0 - i * 0.1) for i in range(len(documents))]

    stages, final = assemble_search(
        chunks, "休学", llm_terms=["学籍"], semantic_results=semantic_results, top_k=5, rerank_fn=fake_rerank
    )
    assert [s.stage for s in stages] == [1, 2, 3, 4, 5]
    assert stages[0].label == "literal"
    assert stages[4].label == "rerank"
    # chunk 1 matches "休学" literally; chunk 2 only shows up via the injected semantic result
    found_ids = {cid for s in stages for cid in s.top_chunk_ids}
    assert {1, 2} <= found_ids
    assert len(final) > 0

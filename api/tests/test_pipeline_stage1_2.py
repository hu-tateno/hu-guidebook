from app.services.search.pipeline import ChunkRecord, literal_search, make_trace


def _chunk(id_, text, page=1, document_id=1, admission_year=2024):
    return ChunkRecord(
        id=id_,
        document_id=document_id,
        admission_year=admission_year,
        page_number=page,
        heading_path=None,
        text=text,
        bbox=[],
    )


def test_literal_search_ranks_by_occurrence_count():
    chunks = [
        _chunk(1, "休学を希望する場合は休学願を提出してください。休学期間は1年以内です。"),
        _chunk(2, "卒業要件は124単位以上の修得です。"),
        _chunk(3, "休学は学務課の窓口で相談できます。"),
    ]
    results = literal_search(chunks, ["休学"])
    assert [sc.chunk.id for sc in results] == [1, 3]
    assert results[0].score == 3  # "休学" appears 3 times in chunk 1
    assert results[1].score == 1


def test_literal_search_is_case_insensitive_for_ascii_terms():
    chunks = [_chunk(1, "GPAの計算方法について説明します。gpa is important.")]
    results = literal_search(chunks, ["gpa"])
    assert len(results) == 1
    assert results[0].score == 2


def test_literal_search_no_match_returns_empty():
    chunks = [_chunk(1, "卒業要件について")]
    assert literal_search(chunks, ["休学"]) == []


def test_literal_search_respects_limit():
    chunks = [_chunk(i, "休学について") for i in range(30)]
    results = literal_search(chunks, ["休学"], limit=5)
    assert len(results) == 5


def test_literal_search_ignores_blank_terms():
    chunks = [_chunk(1, "休学について")]
    results = literal_search(chunks, ["", "  ", "休学"])
    assert len(results) == 1
    assert results[0].matched_terms == ["休学"]


def test_make_trace_summarizes_results():
    chunks = [_chunk(i, "休学について") for i in range(3)]
    results = literal_search(chunks, ["休学"])
    trace = make_trace(1, "literal", ["休学"], results)
    assert trace.stage == 1
    assert trace.label == "literal"
    assert trace.result_count == 3
    assert trace.top_chunk_ids == [0, 1, 2]

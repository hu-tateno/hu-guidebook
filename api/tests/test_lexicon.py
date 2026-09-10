from app.services.lexicon import expand_terms, load_lexicon


def test_load_lexicon_reads_repo_yaml():
    lexicon = load_lexicon()
    assert "休学" in lexicon
    assert lexicon["休学"] == ["休学願", "学籍"]


def test_load_lexicon_missing_file_returns_empty():
    assert load_lexicon("/nonexistent/path.yaml") == {}


def test_expand_terms_matches_substring_in_query():
    lexicon = {"休学": ["休学願", "学籍"], "留年": ["原級"]}
    assert expand_terms("休学したい", lexicon) == ["休学願", "学籍"]


def test_expand_terms_dedupes_across_matching_keys():
    lexicon = {"休学": ["休学願", "学籍"], "退学": ["休学願", "除籍"]}
    # both "休学" and "退学" match the query and both list "休学願"; it must appear once
    result = expand_terms("休学と退学の違い", lexicon)
    assert result == ["休学願", "学籍", "除籍"]


def test_expand_terms_excludes_term_equal_to_query():
    lexicon = {"休学": ["休学"]}
    assert expand_terms("休学", lexicon) == []


def test_expand_terms_no_match_returns_empty():
    lexicon = {"休学": ["休学願"]}
    assert expand_terms("シラバスの見方", lexicon) == []

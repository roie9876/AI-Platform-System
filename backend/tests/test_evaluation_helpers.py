"""Unit tests for evaluation service helper functions."""

from app.services.evaluation_service import _jaccard_similarity, _keyword_match_rate


class TestJaccardSimilarity:
    def test_identical_strings(self):
        assert _jaccard_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert _jaccard_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        result = _jaccard_similarity("hello world foo", "hello world bar")
        # intersection: {hello, world} = 2, union: {hello, world, foo, bar} = 4
        assert result == 0.5

    def test_empty_first(self):
        assert _jaccard_similarity("", "hello world") == 0.0

    def test_empty_second(self):
        assert _jaccard_similarity("hello world", "") == 0.0

    def test_both_empty(self):
        assert _jaccard_similarity("", "") == 0.0

    def test_case_insensitivity(self):
        assert _jaccard_similarity("Hello World", "hello world") == 1.0

    def test_single_word_match(self):
        assert _jaccard_similarity("hello", "hello") == 1.0


class TestKeywordMatchRate:
    def test_all_keywords_present(self):
        assert _keyword_match_rate("the quick brown fox", ["quick", "brown"]) == 1.0

    def test_no_keywords_present(self):
        assert _keyword_match_rate("the quick brown fox", ["missing", "absent"]) == 0.0

    def test_partial_match(self):
        result = _keyword_match_rate("the quick brown fox", ["quick", "missing"])
        assert result == 0.5

    def test_empty_keywords(self):
        assert _keyword_match_rate("some text", []) == 1.0

    def test_case_insensitivity(self):
        assert _keyword_match_rate("The Quick Brown Fox", ["quick", "fox"]) == 1.0

    def test_keyword_substring_match(self):
        # "fox" should be found inside "foxes" since it uses `in`
        assert _keyword_match_rate("the foxes jumped", ["fox"]) == 1.0

import pytest
from sentiment import SentimentAnalyzer


class TestSentimentAnalyzer:
    def test_exists(self):
        sa = SentimentAnalyzer()
        assert sa is not None

    def test_returns_dict(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("hello")
        assert isinstance(result, dict)

    def test_has_expected_keys(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("hello")
        for k in ("happy", "sad", "angry", "neutral"):
            assert k in result

    def test_neutral_default(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("")
        assert result.get("neutral", 0) > 0

    def test_dominant_returns_tuple(self):
        sa = SentimentAnalyzer()
        result = sa.analyze("hello")
        dom = max(result, key=result.get)
        assert isinstance(dom, str)

    def test_non_string_input(self):
        sa = SentimentAnalyzer()
        result = sa.analyze(None)
        assert isinstance(result, dict)

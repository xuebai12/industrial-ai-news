from types import SimpleNamespace

from main import _successful_analyzed_keys


def test_successful_analyzed_keys_uses_original_article_key() -> None:
    ranked_a = SimpleNamespace(url="https://example.com/a", source="s1", title="A")
    ranked_b = SimpleNamespace(url="https://example.com/b", source="s2", title="B")

    analyzed_success = [
        SimpleNamespace(original=ranked_a),
        SimpleNamespace(original=ranked_b),
    ]
    keys = _successful_analyzed_keys(analyzed_success)

    assert "https://example.com/a" in keys
    assert "https://example.com/b" in keys


def test_successful_analyzed_keys_fallbacks_when_original_missing() -> None:
    analyzed_without_original = [SimpleNamespace(source_url="https://example.com/c", source_name="s3")]
    keys = _successful_analyzed_keys(analyzed_without_original)
    assert "https://example.com/c" in keys

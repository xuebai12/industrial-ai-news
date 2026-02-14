import pytest
import sys
import os

# Ensure src is in path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.analyzers.llm_analyzer import _extract_json

class TestExtractJson:
    def test_valid_json(self):
        text = '{"key": "value"}'
        assert _extract_json(text) == {"key": "value"}

    def test_markdown_json(self):
        text = '```json\n{"key": "value"}\n```'
        assert _extract_json(text) == {"key": "value"}

    def test_markdown_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        assert _extract_json(text) == {"key": "value"}

    def test_json_in_text(self):
        text = 'Here is the JSON: {"key": "value"}'
        assert _extract_json(text) == {"key": "value"}

    def test_single_quotes(self):
        text = "{'key': 'value'}"
        assert _extract_json(text) == {"key": "value"}

    def test_trailing_comma(self):
        text = '{"key": "value",}'
        assert _extract_json(text) == {"key": "value"}

    def test_truncated_json(self):
        text = '{"key": "val'
        # Expecting repair to work
        result = _extract_json(text)
        assert result.get("key") == "val"

    def test_empty_input(self):
        assert _extract_json("") is None

    def test_no_json(self):
        text = "Just some text without any braces."
        assert _extract_json(text) is None

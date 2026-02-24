import unittest
import types
import sys

if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

from src.analyzers.llm_analyzer import _extract_json


class TestLLMJsonExtract(unittest.TestCase):
    def test_extracts_valid_json(self):
        data = _extract_json('{"category_tag":"AI","summary_en":"ok"}')
        self.assertIsNotNone(data)
        self.assertEqual(data["category_tag"], "AI")

    def test_recovers_truncated_unclosed_string_and_brace(self):
        raw = '{"category_tag":"Predictive...'
        data = _extract_json(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["category_tag"], "Predictive...")

    def test_recovers_truncated_nested_object(self):
        raw = '{"category_tag":"AI","meta":{"lang":"en"'
        data = _extract_json(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["category_tag"], "AI")
        self.assertEqual(data["meta"]["lang"], "en")

    def test_non_object_json_is_rejected(self):
        self.assertIsNone(_extract_json('["not","an","object"]'))

    def test_recovers_fenced_json_with_unescaped_newline_in_string(self):
        raw = """```json
{
  "category_tag": "Humanoid Robotics / Industry Analysis",
  "summary_en": "First line
Second line"
}
```"""
        data = _extract_json(raw)
        self.assertIsNotNone(data)
        self.assertEqual(data["category_tag"], "Humanoid Robotics / Industry Analysis")
        self.assertEqual(data["summary_en"], "First line\nSecond line")


if __name__ == "__main__":
    unittest.main()

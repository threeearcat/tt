"""Tests for tt.py"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import tt


class TestAutoTarget(unittest.TestCase):
    def test_korean_input_returns_en(self):
        self.assertEqual(tt.auto_target("안녕하세요"), "en")

    def test_english_input_returns_ko(self):
        self.assertEqual(tt.auto_target("hello"), "ko")

    def test_mixed_with_korean_returns_en(self):
        self.assertEqual(tt.auto_target("hello 안녕"), "en")

    def test_empty_returns_ko(self):
        self.assertEqual(tt.auto_target(""), "ko")


class TestLoadConfig(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with patch.object(tt, "CONFIG_PATH", "/nonexistent/config.json"):
            self.assertEqual(tt.load_config(), {})

    def test_valid_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"theme": "nord", "font_size": 16}, f)
            f.flush()
            with patch.object(tt, "CONFIG_PATH", f.name):
                config = tt.load_config()
        os.unlink(f.name)
        self.assertEqual(config, {"theme": "nord", "font_size": 16})

    def test_invalid_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{bad json")
            f.flush()
            with patch.object(tt, "CONFIG_PATH", f.name):
                config = tt.load_config()
        os.unlink(f.name)
        self.assertEqual(config, {})


class TestTranslateAuto(unittest.TestCase):
    @patch("tt.translate", return_value=("안녕", "en"))
    def test_auto_target_english_to_korean(self, mock_translate):
        result = tt.translate_auto("hello")
        mock_translate.assert_called_once_with("hello", target="ko")
        self.assertEqual(result, "안녕")

    @patch("tt.translate", return_value=("hello", "ko"))
    def test_auto_target_korean_to_english(self, mock_translate):
        result = tt.translate_auto("안녕")
        mock_translate.assert_called_once_with("안녕", target="en")
        self.assertEqual(result, "hello")

    @patch("tt.translate", return_value=("こんにちは", "en"))
    def test_fixed_target(self, mock_translate):
        result = tt.translate_auto("hello", fixed_target="ja")
        mock_translate.assert_called_once_with("hello", target="ja")
        self.assertEqual(result, "こんにちは")


if __name__ == "__main__":
    unittest.main()

"""Tests for RFC 5545 line folding, unfolding, and text escaping."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.writer import fold_line, escape_text
from ics_tools.parser import unfold_lines, unescape_text


class TestFoldingAndUnfolding(unittest.TestCase):
    def test_short_line_not_folded(self):
        line = "SUMMARY:Short event"
        folded = fold_line(line)
        self.assertEqual(folded, "SUMMARY:Short event\r\n")

    def test_exact_75_octets_not_folded(self):
        # 75 ASCII characters
        line = "SUMMARY:" + "A" * (75 - len("SUMMARY:"))
        self.assertEqual(len(line.encode("utf-8")), 75)
        folded = fold_line(line)
        self.assertEqual(folded, line + "\r\n")

    def test_folding_ascii_over_75_octets(self):
        # Line of 120 ASCII chars
        line = "DESCRIPTION:" + "x" * 120
        folded = fold_line(line)
        lines = folded.split("\r\n")
        # Should have at least 2 non-empty lines
        content_lines = [l for l in lines if l]
        self.assertGreaterEqual(len(content_lines), 2)

        # Every line must be <= 75 octets
        for l in content_lines:
            self.assertLessEqual(len(l.encode("utf-8")), 75)

        # Continuation lines must begin with a space
        for l in content_lines[1:]:
            self.assertTrue(l.startswith(" "))

        # Roundtrip via unfold
        unfolded = unfold_lines(folded)
        self.assertEqual(len(unfolded), 1)
        self.assertEqual(unfolded[0][1], line)

    def test_folding_utf8_multibyte_characters(self):
        # Turkish and non-ASCII characters: 'ş', 'ğ', 'ı', 'ç', 'ö', 'ü'
        # Each is 2 bytes in UTF-8
        turkish_text = "Öğleden sonra İstanbul Kadıköy'de Türkçe buluşma ve çalıştay planlandı. Katılımcıların listesi hazır."
        line = f"SUMMARY:{turkish_text}"
        folded = fold_line(line)

        # Check line limits
        lines = [l for l in folded.split("\r\n") if l]
        for l in lines:
            self.assertLessEqual(len(l.encode("utf-8")), 75)
            # Ensure valid UTF-8 decoding
            l.encode("utf-8").decode("utf-8")

        # Unfold and compare exact equality
        unfolded = unfold_lines(folded)
        self.assertEqual(len(unfolded), 1)
        self.assertEqual(unfolded[0][1], line)

    def test_folding_with_emojis_4_byte_utf8(self):
        # 4-byte UTF-8 emojis
        emoji_text = "Conference 🚀📅🎉 with team in Tokyo 🗾🗼 and London 🇬🇧" * 4
        line = f"DESCRIPTION:{emoji_text}"
        folded = fold_line(line)

        lines = [l for l in folded.split("\r\n") if l]
        for l in lines:
            self.assertLessEqual(len(l.encode("utf-8")), 75)
            # Ensure valid UTF-8 decoding
            l.encode("utf-8").decode("utf-8")

        unfolded = unfold_lines(folded)
        self.assertEqual(len(unfolded), 1)
        self.assertEqual(unfolded[0][1], line)

    def test_unfold_variations_crlf_and_lf(self):
        # Test CRLF continuation with space and tab
        raw_crlf = "SUMMARY:This is a very long \r\n line with CRLF\r\n\tand a tab\r\n"
        unfolded = unfold_lines(raw_crlf)
        self.assertEqual(len(unfolded), 1)
        self.assertEqual(unfolded[0][1], "SUMMARY:This is a very long line with CRLFand a tab")

        # Test bare LF continuation
        raw_lf = "DESCRIPTION:First part\n of description\nSECOND:Standalone\n"
        unfolded_lf = unfold_lines(raw_lf)
        self.assertEqual(len(unfolded_lf), 2)
        self.assertEqual(unfolded_lf[0][1], "DESCRIPTION:First partof description")
        self.assertEqual(unfolded_lf[1][1], "SECOND:Standalone")


class TestEscapingAndUnescaping(unittest.TestCase):
    def test_escaping_special_characters(self):
        raw = "Hello, world; how are you? \\ Backslash \n New line"
        escaped = escape_text(raw)
        self.assertIn(r"\,", escaped)
        self.assertIn(r"\;", escaped)
        self.assertIn(r"\\", escaped)
        self.assertIn(r"\n", escaped)

        unescaped = unescape_text(escaped)
        self.assertEqual(unescaped, raw)

    def test_unescaping_capital_n(self):
        raw = r"Line 1\NLine 2"
        self.assertEqual(unescape_text(raw), "Line 1\nLine 2")

    def test_empty_string(self):
        self.assertEqual(escape_text(""), "")
        self.assertEqual(unescape_text(""), "")


if __name__ == "__main__":
    unittest.main()

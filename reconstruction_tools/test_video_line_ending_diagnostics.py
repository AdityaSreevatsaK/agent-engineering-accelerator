"""Guard video-editor count diagnostics against silent newline assumptions.

These are infrastructure tests; they neither reconstruct original footage
nor assert historical byte identity.
"""
from __future__ import annotations

import unittest

from reconstruction_tools.audit_original_example_test_counts import editor_counts, observed_line_endings


class VideoLineEndingDiagnosticsTests(unittest.TestCase):
    def test_lf_counts_include_blank_final_editor_line(self):
        self.assertEqual(editor_counts(b"a\nb\n", "LF"), (3, 4))
        self.assertEqual(observed_line_endings(b"a\nb\n"), "LF")

    def test_crlf_editor_counts_reconstruct_original_character_convention(self):
        source = b"a\r\nb\r\n"
        self.assertEqual(editor_counts(source, "CRLF"), (3, 6))
        self.assertEqual(observed_line_endings(source), "CRLF")

    def test_checkout_translation_is_reported_not_hidden(self):
        source = b"a\nb\n"
        self.assertEqual(editor_counts(source, "CRLF"), (3, 6))
        self.assertEqual(observed_line_endings(source), "LF")

    def test_mixed_endings_are_visible(self):
        self.assertEqual(observed_line_endings(b"a\r\nb\nc\r"), "CRLF+LF+CR")

    def test_bom_does_not_inflate_editor_character_count(self):
        self.assertEqual(editor_counts(b"\xef\xbb\xbfa\n", "LF"), (2, 2))

    def test_empty_file_has_no_newline_style(self):
        self.assertEqual(observed_line_endings(b""), "none")
        self.assertEqual(editor_counts(b"", "LF"), (1, 0))


if __name__ == "__main__":
    unittest.main()

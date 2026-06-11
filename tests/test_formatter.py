import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from telegram_deleted_messages.formatter import (
    build_blocks,
    convert_messages,
    format_links,
    split_text,
)


class FormatterTests(unittest.TestCase):
    def test_format_links_skips_empty_urls(self):
        links = [
            {"text": "Example", "url": "https://example.com"},
            {"text": "", "url": ""},
            {"text": "https://openai.com", "url": "https://openai.com"},
        ]

        result = format_links(links)

        self.assertIn("Example: https://example.com", result)
        self.assertIn("- https://openai.com", result)
        self.assertNotIn('""', result)

    def test_split_text_prefers_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."

        chunks = split_text(text, 31)

        self.assertEqual(chunks, ["First sentence.", "Second sentence.", "Third sentence."])

    def test_build_blocks_appends_links_to_last_part(self):
        messages = [
            {
                "deleted_at": "2026-01-01 00:00:00+00:00",
                "message_date": "2025-12-31 00:00:00+00:00",
                "message_id": 10,
                "text": "A" * 1200,
                "links": [{"text": "Example", "url": "https://example.com"}],
            }
        ]

        blocks = build_blocks(messages, max_length=1150)

        self.assertEqual(len(blocks), 2)
        self.assertNotIn("Links:", blocks[0])
        self.assertIn("Links:", blocks[1])

    def test_convert_messages_writes_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messages.json"
            output = Path(tmp) / "messages.txt"
            source.write_text(
                json.dumps(
                    [
                        {
                            "deleted_at": "2026-01-01",
                            "message_date": "2025-12-31",
                            "message_id": 1,
                            "text": "hello",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                convert_messages(source, output, 3900)

            self.assertIn("hello", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

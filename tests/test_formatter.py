import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from telegram_deleted_messages.formatter import (
    build_html,
    build_blocks,
    build_markdown,
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
                convert_messages(source, output, 3900, "txt")

            self.assertIn("hello", output.read_text(encoding="utf-8"))

    def test_build_markdown_includes_edit_diff(self):
        messages = [
            {
                "event_type": "edit",
                "event_id": 5,
                "message_id": 1,
                "message_date": "2026-01-01",
                "edited_at": "2026-01-02",
                "sender": {"id": 10, "username": "sender", "display_name": "Sender Name"},
                "actor": {"id": 20, "username": "admin", "display_name": "Admin Name"},
                "prev_text": "before",
                "new_text": "after",
                "text_diff": {"lines": ["--- prev_text", "+++ new_text", "-before", "+after"]},
                "new_links": [{"text": "Example", "url": "https://example.com"}],
            }
        ]

        result = build_markdown(messages)

        self.assertIn("## 1. EDIT message 1", result)
        self.assertIn("- Sender: Sender Name @sender (10)", result)
        self.assertIn("- Actor: Admin Name @admin (20)", result)
        self.assertIn("```diff", result)
        self.assertIn("-before", result)
        self.assertIn("[Example](https://example.com)", result)

    def test_build_html_escapes_text_and_links(self):
        messages = [
            {
                "event_type": "delete",
                "event_id": 5,
                "message_id": 1,
                "message_date": "2026-01-01",
                "deleted_at": "2026-01-02",
                "text": "<hello>",
                "links": [{"text": "<Example>", "url": "https://example.com/?a=1&b=2"}],
            }
        ]

        result = build_html(messages)

        self.assertIn('<article class="message color0">', result)
        self.assertIn('<div class="meta">', result)
        self.assertIn("&lt;hello&gt;", result)
        self.assertIn("&lt;Example&gt;", result)
        self.assertIn("https://example.com/?a=1&amp;b=2", result)

    def test_build_html_separates_senders_with_compact_meta(self):
        messages = [
            {
                "event_type": "delete",
                "event_id": 5,
                "message_id": 1,
                "message_date": "2026-01-01",
                "deleted_at": "2026-01-02",
                "sender": {"id": 10, "username": "first", "display_name": "First User"},
                "actor": {"id": 20, "username": "admin", "display_name": "Admin User"},
                "text": "first message",
            },
            {
                "event_type": "delete",
                "event_id": 6,
                "message_id": 2,
                "message_date": "2026-01-03",
                "deleted_at": "2026-01-04",
                "sender": {"id": 11, "username": "second", "display_name": "Second User"},
                "actor": {"id": 20, "username": "admin", "display_name": "Admin User"},
                "text": "second message",
            },
        ]

        result = build_html(messages)

        self.assertIn('<main id="chat">', result)
        self.assertIn('<article class="message color0">', result)
        self.assertIn('<article class="message color1">', result)
        self.assertIn('<div class="sender">First User @first (10)</div>', result)
        self.assertIn('<div class="sender">Second User @second (11)</div>', result)
        self.assertIn("message: 2026-01-01 | event: 2026-01-02 | actor: Admin User @admin (20) | event id: 5", result)

    def test_convert_messages_writes_markdown_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "messages.json"
            md_output = Path(tmp) / "messages.md"
            html_output = Path(tmp) / "messages.html"
            source.write_text(
                json.dumps(
                    [
                        {
                            "event_type": "delete",
                            "event_id": 1,
                            "message_id": 1,
                            "message_date": "2026-01-01",
                            "deleted_at": "2026-01-02",
                            "text": "hello",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                convert_messages(source, md_output, 3900, "md")
                convert_messages(source, html_output, 3900, "html")

            self.assertIn("# Telegram Admin Log Export", md_output.read_text(encoding="utf-8"))
            self.assertIn("<!doctype html>", html_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

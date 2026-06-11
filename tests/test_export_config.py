import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_deleted_messages.export import (
    bool_env,
    build_parser,
    load_config,
    load_env_file,
)


class ExportConfigTests(unittest.TestCase):
    def write_config(self, directory, extra=""):
        path = Path(directory) / "secrets.env"
        path.write_text(
            "\n".join(
                [
                    "TELEGRAM_API_ID=12345",
                    "TELEGRAM_API_HASH=test_hash",
                    "TELEGRAM_CHAT=@test_chat",
                    "TELEGRAM_SESSION=config/test_session",
                    "TELEGRAM_ADMIN_LOG_LIMIT=250",
                    "TELEGRAM_MIN_TEXT_LENGTH=42",
                    "TELEGRAM_OUTPUT_FILE=deleted_test.json",
                    extra,
                ]
            ),
            encoding="utf-8",
        )
        return path

    def test_load_env_file_reads_key_values_without_overriding_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.write_config(tmp)
            with patch.dict(os.environ, {"TELEGRAM_CHAT": "@from_env"}, clear=True):
                load_env_file(config_file)

                self.assertEqual(os.environ["TELEGRAM_API_ID"], "12345")
                self.assertEqual(os.environ["TELEGRAM_CHAT"], "@from_env")

    def test_load_config_uses_env_file_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.write_config(tmp)
            parser = build_parser()

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(parser.parse_args(["--config", str(config_file)]))

            self.assertEqual(config.api_id, 12345)
            self.assertEqual(config.api_hash, "test_hash")
            self.assertEqual(config.chat, "@test_chat")
            self.assertEqual(config.limit, 250)
            self.assertEqual(config.min_text_length, 42)
            self.assertEqual(config.output_file, Path("deleted_test.json"))
            self.assertEqual(config.session, Path("config/test_session"))

    def test_cli_flags_override_export_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.write_config(tmp)
            parser = build_parser()
            args = parser.parse_args(
                [
                    "--config",
                    str(config_file),
                    "--all",
                    "--text-only",
                    "--with-links",
                    "--download-media",
                    "--media-dir",
                    "media_test",
                    "--output",
                    "out.json",
                ]
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(args)

            self.assertEqual(config.min_text_length, 0)
            self.assertTrue(config.text_only)
            self.assertTrue(config.with_links)
            self.assertTrue(config.download_media)
            self.assertEqual(config.media_dir, Path("media_test"))
            self.assertEqual(config.output_file, Path("out.json"))

    def test_bool_env_rejects_invalid_values(self):
        with patch.dict(os.environ, {"TELEGRAM_WITH_LINKS": "maybe"}, clear=True):
            with self.assertRaises(SystemExit):
                bool_env("TELEGRAM_WITH_LINKS")


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telegram_deleted_messages.export import (
    bool_env,
    build_parser,
    default_checkpoint_file,
    default_output_file,
    load_config,
    load_checkpoint,
    load_env_file,
    load_existing_messages,
    merge_messages,
    parse_events,
    safe_filename_part,
    save_checkpoint,
    sort_messages,
    smoke_test_main,
    write_export,
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
                    "TELEGRAM_OUTPUT_FILE=",
                    "TELEGRAM_EVENTS=delete",
                    "TELEGRAM_INCREMENTAL=false",
                    "TELEGRAM_SENDER_ID=",
                    "TELEGRAM_DELETED_BY=",
                    "TELEGRAM_HAS_MEDIA=false",
                    "TELEGRAM_HAS_LINKS=false",
                    "TELEGRAM_SORT_BY=none",
                    "TELEGRAM_SORT_ORDER=asc",
                    "TELEGRAM_RESOLVE_USERS=false",
                    "TELEGRAM_CHECKPOINT=false",
                    "TELEGRAM_CHECKPOINT_FILE=",
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
            self.assertEqual(config.output_file, Path("test_chat_admin_log.json"))
            self.assertEqual(config.session, Path("config/test_session"))

    def test_default_output_file_uses_safe_chat_name(self):
        self.assertEqual(default_output_file("@test/chat"), Path("test_chat_admin_log.json"))
        self.assertEqual(safe_filename_part("@group.name"), "group.name")
        self.assertEqual(
            default_checkpoint_file("@test/chat"),
            Path("state/test_chat_checkpoint.json"),
        )

    def test_checkpoint_read_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"

            self.assertEqual(load_checkpoint(path), 0)
            save_checkpoint(path, 123)

            self.assertEqual(load_checkpoint(path), 123)

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
                    "--incremental",
                    "--media-dir",
                    "media_test",
                    "--output",
                    "out.json",
                    "--sender-id",
                    "111",
                    "--deleted-by",
                    "222",
                    "--has-media",
                    "--has-links",
                    "--events",
                    "delete,edit",
                    "--sort-by",
                    "message-date",
                    "--sort-order",
                    "desc",
                    "--resolve-users",
                    "--checkpoint",
                    "--checkpoint-file",
                    "state/custom.json",
                ]
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(args)

            self.assertEqual(config.min_text_length, 0)
            self.assertTrue(config.text_only)
            self.assertTrue(config.with_links)
            self.assertTrue(config.download_media)
            self.assertTrue(config.incremental)
            self.assertEqual(config.media_dir, Path("media_test"))
            self.assertEqual(config.output_file, Path("out.json"))
            self.assertEqual(config.sender_id, 111)
            self.assertEqual(config.deleted_by, 222)
            self.assertTrue(config.has_media)
            self.assertTrue(config.has_links)
            self.assertEqual(config.events, ("delete", "edit"))
            self.assertEqual(config.sort_by, "message-date")
            self.assertEqual(config.sort_order, "desc")
            self.assertTrue(config.resolve_users)
            self.assertTrue(config.checkpoint)
            self.assertEqual(config.checkpoint_file, Path("state/custom.json"))

    def test_bool_env_rejects_invalid_values(self):
        with patch.dict(os.environ, {"TELEGRAM_WITH_LINKS": "maybe"}, clear=True):
            with self.assertRaises(SystemExit):
                bool_env("TELEGRAM_WITH_LINKS")

    def test_parse_events_rejects_unknown_event(self):
        with self.assertRaises(SystemExit):
            parse_events("delete,join")

    def test_incremental_write_merges_existing_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "deleted.json"
            output.write_text(
                '[{"delete_event_id": 1, "text": "old"}]',
                encoding="utf-8",
            )
            config_file = self.write_config(tmp)
            parser = build_parser()

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(
                    parser.parse_args(
                        [
                            "--config",
                            str(config_file),
                            "--incremental",
                            "--output",
                            str(output),
                        ]
                    )
                )

            merged, added, skipped = write_export(
                config,
                [
                    {"delete_event_id": 1, "text": "duplicate"},
                    {"delete_event_id": 2, "text": "new"},
                ],
            )

            self.assertEqual(added, 1)
            self.assertEqual(skipped, 1)
            self.assertEqual([item["delete_event_id"] for item in merged], [1, 2])
            self.assertEqual(merged[0]["text"], "duplicate")
            self.assertEqual(load_existing_messages(output), merged)

    def test_merge_messages_deduplicates_existing_duplicates(self):
        merged, added, skipped = merge_messages(
            [
                {"delete_event_id": 1, "text": "first"},
                {"delete_event_id": 1, "text": "duplicate"},
            ],
            [{"delete_event_id": 2, "text": "new"}],
        )

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 1)
        self.assertEqual([item["delete_event_id"] for item in merged], [1, 2])

    def test_sort_messages_by_message_date(self):
        messages = [
            {"message_id": 2, "message_date": "2026-01-02 00:00:00+00:00"},
            {"message_id": 1, "message_date": "2026-01-01 00:00:00+00:00"},
        ]

        result = sort_messages(messages, "message-date", "asc")

        self.assertEqual([message["message_id"] for message in result], [1, 2])

    def test_write_export_sorts_incremental_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "deleted.json"
            output.write_text(
                '[{"delete_event_id": 2, "message_date": "2026-01-02"}]',
                encoding="utf-8",
            )
            config_file = self.write_config(tmp)
            parser = build_parser()

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(
                    parser.parse_args(
                        [
                            "--config",
                            str(config_file),
                            "--incremental",
                            "--sort-by",
                            "message-date",
                            "--output",
                            str(output),
                        ]
                    )
                )

            merged, _, _ = write_export(
                config,
                [{"delete_event_id": 1, "message_date": "2026-01-01"}],
            )

            self.assertEqual([message["delete_event_id"] for message in merged], [1, 2])

    def test_smoke_test_main_builds_small_export_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = self.write_config(tmp)
            output = Path(tmp) / "smoke.json"

            with patch("telegram_deleted_messages.export.export_deleted_messages") as export:
                smoke_test_main(
                    [
                        "--config",
                        str(config_file),
                        "--limit",
                        "7",
                        "--output",
                        str(output),
                    ]
                )

            config = export.call_args.args[0]
            self.assertEqual(config.limit, 7)
            self.assertEqual(config.output_file, output)
            self.assertEqual(config.min_text_length, 0)
            self.assertTrue(config.with_links)
            self.assertFalse(config.download_media)
            self.assertFalse(config.incremental)


if __name__ == "__main__":
    unittest.main()

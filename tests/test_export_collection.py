import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from telegram_deleted_messages.export import ExportConfig, collect_deleted_messages

try:
    from telethon import types

    TELETHON_AVAILABLE = True
except ModuleNotFoundError:
    types = None
    TELETHON_AVAILABLE = False


class FakeMedia:
    pass


class FakeMessage:
    def __init__(self, message_id, text, media=None):
        self.id = message_id
        self.message = text
        self.date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.from_id = SimpleNamespace(user_id=777)
        self.media = media

    def get_entities_text(self):
        return []


class FakeEvent:
    def __init__(self, event_id, message):
        self.id = event_id
        self.date = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.user_id = 999
        self.action = types.ChannelAdminLogEventActionDeleteMessage(message)


class FakeClient:
    def __init__(self, events):
        self.events = events
        self.downloads = []

    def iter_admin_log(self, entity, limit, delete):
        self.iter_args = (entity, limit, delete)
        return iter(self.events[:limit])

    def download_media(self, message, file):
        self.downloads.append((message.id, file))
        return str(Path(file) / f"{message.id}.bin")


@unittest.skipUnless(TELETHON_AVAILABLE, "Telethon is required for export tests")
class ExportCollectionTests(unittest.TestCase):
    def make_config(self, **overrides):
        values = {
            "api_id": 123,
            "api_hash": "hash",
            "chat": "@chat",
            "limit": 100,
            "min_text_length": 5,
            "output_file": Path("out.json"),
            "session": Path("config/session"),
            "config_file": Path("config/secrets.env"),
            "text_only": False,
            "with_links": False,
            "download_media": False,
            "media_dir": Path("media"),
            "incremental": False,
        }
        values.update(overrides)
        return ExportConfig(**values)

    def collect_quietly(self, client, entity, config):
        with redirect_stdout(StringIO()):
            return collect_deleted_messages(client, entity, config)

    def test_collect_deleted_messages_filters_short_text(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "long enough")),
                FakeEvent(2, FakeMessage(11, "no")),
            ]
        )

        result = self.collect_quietly(client, "entity", self.make_config())

        self.assertEqual(client.iter_args, ("entity", 100, True))
        self.assertEqual([item["message_id"] for item in result], [10])
        self.assertNotIn("links", result[0])

    def test_all_includes_short_and_media_only_messages(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "x")),
                FakeEvent(2, FakeMessage(11, "", media=FakeMedia())),
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, with_links=True),
        )

        self.assertEqual([item["message_id"] for item in result], [10, 11])
        self.assertEqual(result[0]["links"], [])
        self.assertTrue(result[1]["has_media"])
        self.assertEqual(result[1]["media"]["type"], "FakeMedia")

    def test_text_only_skips_media_only_messages(self):
        client = FakeClient([FakeEvent(1, FakeMessage(10, "", media=FakeMedia()))])

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, text_only=True),
        )

        self.assertEqual(result, [])

    def test_download_media_keeps_short_media_message_and_records_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient([FakeEvent(1, FakeMessage(10, "", media=FakeMedia()))])

            result = self.collect_quietly(
                client,
                "entity",
                self.make_config(
                    min_text_length=100,
                    download_media=True,
                    media_dir=Path(tmp),
                ),
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(client.downloads[0][0], 10)
        self.assertTrue(result[0]["media"]["downloaded_path"].endswith("10.bin"))
        self.assertIsNone(result[0]["media"]["download_error"])


if __name__ == "__main__":
    unittest.main()

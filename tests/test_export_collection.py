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


class FakeUser:
    def __init__(self, user_id, username=None, first_name=None, last_name=None):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name


class FakeMessage:
    def __init__(self, message_id, text, media=None, sender=777, links=None):
        self.id = message_id
        self.message = text
        self.date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.from_id = SimpleNamespace(user_id=sender)
        self.media = media
        self.links = links or []

    def get_entities_text(self):
        return self.links


class FakeEvent:
    def __init__(self, event_id, message, deleted_by=999):
        self.id = event_id
        self.date = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.user_id = deleted_by
        self.action = types.ChannelAdminLogEventActionDeleteMessage(message)


class FakeEditEvent:
    def __init__(self, event_id, prev_message, new_message, edited_by=999):
        self.id = event_id
        self.date = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.user_id = edited_by
        self.action = types.ChannelAdminLogEventActionEditMessage(
            prev_message,
            new_message,
        )


class FakeClient:
    def __init__(self, events, entities=None):
        self.events = events
        self.downloads = []
        self.entities = entities or {}
        self.get_entity_calls = []

    def iter_admin_log(self, entity, limit, min_id=0, delete=False, edit=False):
        self.iter_args = (entity, limit, min_id, delete, edit)
        return iter(self.events[:limit])

    def get_entity(self, entity_id):
        self.get_entity_calls.append(entity_id)
        entity = self.entities.get(entity_id)
        if isinstance(entity, Exception):
            raise entity
        return entity

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
            "sender_id": None,
            "deleted_by": None,
            "has_media": False,
            "has_links": False,
            "sort_by": "none",
            "sort_order": "asc",
            "resolve_users": False,
            "events": ("delete",),
            "checkpoint": False,
            "checkpoint_file": Path("state/test_checkpoint.json"),
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

        self.assertEqual(client.iter_args, ("entity", 100, 0, True, False))
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

    def test_sender_id_filter(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "first", sender=111)),
                FakeEvent(2, FakeMessage(11, "second", sender=222)),
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, sender_id=222),
        )

        self.assertEqual([item["message_id"] for item in result], [11])

    def test_deleted_by_filter(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "first"), deleted_by=111),
                FakeEvent(2, FakeMessage(11, "second"), deleted_by=222),
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, deleted_by=111),
        )

        self.assertEqual([item["message_id"] for item in result], [10])

    def test_has_media_filter(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "text")),
                FakeEvent(2, FakeMessage(11, "photo", media=FakeMedia())),
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, has_media=True),
        )

        self.assertEqual([item["message_id"] for item in result], [11])

    def test_has_links_filter_extracts_links_without_writing_them_by_default(self):
        link_entity = types.MessageEntityUrl(offset=0, length=19)
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "plain text")),
                FakeEvent(
                    2,
                    FakeMessage(
                        11,
                        "https://example.com",
                        links=[(link_entity, "https://example.com")],
                    ),
                ),
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, has_links=True),
        )

        self.assertEqual([item["message_id"] for item in result], [11])
        self.assertNotIn("links", result[0])

    def test_has_links_with_links_writes_extracted_links(self):
        link_entity = types.MessageEntityUrl(offset=0, length=19)
        client = FakeClient(
            [
                FakeEvent(
                    1,
                    FakeMessage(
                        10,
                        "https://example.com",
                        links=[(link_entity, "https://example.com")],
                    ),
                )
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, has_links=True, with_links=True),
        )

        self.assertEqual(result[0]["links"][0]["url"], "https://example.com")

    def test_resolve_users_adds_sender_and_deleter_summaries(self):
        client = FakeClient(
            [FakeEvent(1, FakeMessage(10, "hello", sender=111), deleted_by=222)],
            entities={
                111: FakeUser(111, username="sender", first_name="Send", last_name="Er"),
                222: FakeUser(222, username="admin", first_name="Admin"),
            },
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, resolve_users=True),
        )

        self.assertEqual(result[0]["sender"]["username"], "sender")
        self.assertEqual(result[0]["sender"]["nick"], "@sender")
        self.assertEqual(result[0]["sender"]["display_name"], "Send Er")
        self.assertEqual(result[0]["sender"]["name"], "Send Er")
        self.assertEqual(result[0]["deleted_by_user"]["username"], "admin")
        self.assertEqual(result[0]["deleted_by_user"]["nick"], "@admin")
        self.assertEqual(client.get_entity_calls, [111, 222])

    def test_resolve_users_caches_entities_and_records_errors(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "first", sender=111), deleted_by=222),
                FakeEvent(2, FakeMessage(11, "second", sender=111), deleted_by=333),
            ],
            entities={
                111: FakeUser(111, username="sender"),
                222: FakeUser(222, username="admin"),
                333: ValueError("not found"),
            },
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, resolve_users=True),
        )

        self.assertEqual(client.get_entity_calls, [111, 222, 333])
        self.assertEqual(result[1]["sender"]["username"], "sender")
        self.assertIn("ValueError", result[1]["deleted_by_user"]["resolve_error"])

    def test_edit_event_exports_previous_and_new_text(self):
        client = FakeClient(
            [
                FakeEditEvent(
                    1,
                    FakeMessage(10, "before", sender=111),
                    FakeMessage(10, "after", sender=111),
                    edited_by=222,
                )
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, events=("edit",)),
        )

        self.assertEqual(client.iter_args, ("entity", 100, 0, False, True))
        self.assertEqual(result[0]["event_type"], "edit")
        self.assertEqual(result[0]["prev_text"], "before")
        self.assertEqual(result[0]["new_text"], "after")
        self.assertEqual(result[0]["edited_by"], 222)
        self.assertEqual(result[0]["text_diff"]["format"], "unified")
        self.assertIn("-before", result[0]["text_diff"]["lines"])
        self.assertIn("+after", result[0]["text_diff"]["lines"])
        self.assertEqual(result[0]["text_diff"]["added_lines"], 1)
        self.assertEqual(result[0]["text_diff"]["removed_lines"], 1)

    def test_delete_and_edit_events_can_be_exported_together(self):
        client = FakeClient(
            [
                FakeEvent(1, FakeMessage(10, "deleted")),
                FakeEditEvent(
                    2,
                    FakeMessage(11, "old"),
                    FakeMessage(11, "new"),
                ),
            ]
        )

        result = self.collect_quietly(
            client,
            "entity",
            self.make_config(min_text_length=0, events=("delete", "edit")),
        )

        self.assertEqual(client.iter_args, ("entity", 100, 0, True, True))
        self.assertEqual([item["event_type"] for item in result], ["delete", "edit"])

    def test_checkpoint_min_id_is_passed_and_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "checkpoint.json"
            checkpoint.write_text('{"last_event_id": 5}', encoding="utf-8")
            client = FakeClient(
                [
                    FakeEvent(6, FakeMessage(10, "first")),
                    FakeEvent(8, FakeMessage(11, "second")),
                ]
            )

            result = self.collect_quietly(
                client,
                "entity",
                self.make_config(
                    min_text_length=0,
                    checkpoint=True,
                    checkpoint_file=checkpoint,
                ),
            )

            self.assertEqual(client.iter_args, ("entity", 100, 5, True, False))
            self.assertEqual([item["event_id"] for item in result], [6, 8])
            self.assertIn('"last_event_id": 8', checkpoint.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

import argparse
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path


DEFAULT_CONFIG_FILE = Path("config/secrets.env")


@dataclass(frozen=True)
class ExportConfig:
    api_id: int
    api_hash: str
    chat: str
    limit: int
    min_text_length: int
    output_file: Path
    session: Path
    config_file: Path
    text_only: bool
    with_links: bool
    download_media: bool
    media_dir: Path
    incremental: bool


def load_env_file(path):
    if not path.exists():
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(
                f"Invalid config line {path}:{line_number}: expected KEY=VALUE"
            )

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def required_env(name, config_file):
    value = os.environ.get(name)
    if value:
        return value
    raise SystemExit(
        f"Missing {name}. Set it in environment or create {config_file} "
        "from config/secrets.env.example."
    )


def int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        raise SystemExit(f"Invalid {name}: expected integer.")


def bool_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SystemExit(f"Invalid {name}: expected true or false.")


def ask_phone():
    return input("Enter phone in international format: ").strip()


def ask_code():
    return input("Enter Telegram code: ").strip()


def ask_password():
    return input("Enter Telegram 2FA cloud password: ").strip()


def authorize(client):
    from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError

    if client.is_user_authorized():
        print("Saved session is already authorized.")
        return

    phone = ask_phone()
    print("Sending code request...", flush=True)
    client.send_code_request(phone)

    code = ask_code()
    print("Checking code...", flush=True)
    try:
        client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        print("Telegram 2FA cloud password is enabled.", flush=True)
        password = ask_password()
        print("Checking 2FA password...", flush=True)
        client.sign_in(password=password)
    except PhoneCodeInvalidError:
        raise SystemExit("Error: invalid Telegram code.")


def sender_id(message):
    from_id = getattr(message, "from_id", None)
    if from_id is None:
        return None
    return getattr(from_id, "user_id", None) or getattr(from_id, "channel_id", None)


def append_link(links, seen, kind, url, text=None):
    if not url or url in seen:
        return
    seen.add(url)
    links.append({"kind": kind, "url": url, "text": text or ""})


def extract_links(message):
    from telethon import types

    links = []
    seen = set()

    for entity, inner_text in message.get_entities_text():
        if isinstance(entity, types.MessageEntityTextUrl):
            append_link(links, seen, "text_url", entity.url, inner_text)
        elif isinstance(entity, types.MessageEntityUrl):
            append_link(links, seen, "url", inner_text, inner_text)
        elif isinstance(entity, types.MessageEntityEmail):
            append_link(links, seen, "email", f"mailto:{inner_text}", inner_text)

    webpage = getattr(message, "web_preview", None)
    if webpage is None:
        webpage = getattr(getattr(message, "media", None), "webpage", None)

    append_link(links, seen, "webpage", getattr(webpage, "url", None))
    append_link(links, seen, "webpage_display", getattr(webpage, "display_url", None))

    reply_markup = getattr(message, "reply_markup", None)
    for row in getattr(reply_markup, "rows", []) or []:
        for button in getattr(row, "buttons", []) or []:
            append_link(
                links,
                seen,
                "button",
                getattr(button, "url", None),
                getattr(button, "text", None),
            )

    return links


def media_summary(message, media_result=None):
    media = getattr(message, "media", None)
    if media is None and media_result is None:
        return None

    summary = {
        "type": type(media).__name__ if media is not None else None,
        "downloaded_path": None,
        "download_error": None,
    }
    if media_result is not None:
        summary.update(media_result)
    return summary


def download_message_media(client, message, media_dir):
    if getattr(message, "media", None) is None:
        return None

    message_dir = media_dir / str(message.id)
    message_dir.mkdir(parents=True, exist_ok=True)

    try:
        downloaded_path = client.download_media(message, file=str(message_dir))
    except Exception as exc:
        return {
            "downloaded_path": None,
            "download_error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "downloaded_path": str(downloaded_path) if downloaded_path else None,
        "download_error": None,
    }


def collect_deleted_messages(
    client,
    entity,
    config,
):
    from telethon import types

    print(f"Loading deleted-message events from {config.chat}...")
    deleted_messages = []
    checked_events = 0
    checked_deleted_messages = 0
    skipped_by_text_filter = 0

    for event in client.iter_admin_log(entity, limit=config.limit, delete=True):
        checked_events += 1
        action = event.action

        if not isinstance(action, types.ChannelAdminLogEventActionDeleteMessage):
            continue

        message = getattr(action, "message", None)
        if message is None:
            continue

        checked_deleted_messages += 1
        text = message.message or ""
        has_text = bool(text.strip())
        has_media = getattr(message, "media", None) is not None

        if config.text_only and not has_text:
            skipped_by_text_filter += 1
            continue
        include_for_media_download = config.download_media and has_media
        if len(text) < config.min_text_length and not include_for_media_download:
            skipped_by_text_filter += 1
            continue

        media_result = None
        if config.download_media:
            media_result = download_message_media(client, message, config.media_dir)

        item = {
            "delete_event_id": event.id,
            "deleted_at": str(event.date),
            "deleted_by": event.user_id,
            "message_id": message.id,
            "message_date": str(message.date),
            "sender_id": sender_id(message),
            "text_length": len(text),
            "text": text,
            "has_media": has_media,
        }

        media = media_summary(message, media_result)
        if media is not None:
            item["media"] = media
        if config.with_links:
            item["links"] = extract_links(message)

        deleted_messages.append(item)

        if len(deleted_messages) % 100 == 0:
            print(f"Found deleted messages: {len(deleted_messages)}")

        if checked_deleted_messages % 1000 == 0:
            print(
                f"Checked deleted messages: {checked_deleted_messages}; "
                f"exported: {len(deleted_messages)}"
            )

    print(f"Checked admin-log events: {checked_events}")
    print(f"Checked deleted messages: {checked_deleted_messages}")
    print(f"Skipped by text filter: {skipped_by_text_filter}")
    print(f"Minimum text length: {config.min_text_length}")

    return deleted_messages


def message_key(message):
    key = message.get("delete_event_id")
    if key is not None:
        return ("delete_event_id", key)
    return ("message_id", message.get("message_id"))


def load_existing_messages(path):
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"]
    raise SystemExit(f"Invalid existing export file: {path}")


def merge_messages(existing_messages, new_messages):
    merged = []
    seen = set()
    skipped_duplicates = 0

    for message in existing_messages:
        key = message_key(message)
        if key in seen:
            skipped_duplicates += 1
            continue
        seen.add(key)
        merged.append(message)

    added = 0
    for message in new_messages:
        key = message_key(message)
        if key in seen:
            skipped_duplicates += 1
            continue
        seen.add(key)
        merged.append(message)
        added += 1

    return merged, added, skipped_duplicates


def write_export(config, messages):
    if not config.incremental:
        config.output_file.write_text(
            json.dumps(messages, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        return messages, len(messages), 0

    existing_messages = load_existing_messages(config.output_file)
    merged_messages, added, skipped_duplicates = merge_messages(
        existing_messages,
        messages,
    )
    config.output_file.write_text(
        json.dumps(merged_messages, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    return merged_messages, added, skipped_duplicates


def build_parser():
    parser = argparse.ArgumentParser(
        description="Export deleted Telegram messages from a chat admin log."
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("TELEGRAM_CONFIG_FILE", str(DEFAULT_CONFIG_FILE)),
        help="Path to env file with Telegram settings.",
    )
    parser.add_argument("--chat", help="Telegram group/channel username or id.")
    parser.add_argument("--limit", type=int, help="Admin log events limit.")
    parser.add_argument(
        "--min-text-length",
        type=int,
        help="Skip messages shorter than this number of characters.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export all deleted messages, including short and media-only messages.",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Export only deleted messages that contain text.",
    )
    parser.add_argument(
        "--with-links",
        action="store_true",
        help="Extract message entities, web previews, and button links.",
    )
    parser.add_argument(
        "--download-media",
        action="store_true",
        help="Download media from deleted messages when Telegram still provides it.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Merge with the existing output file and skip duplicate delete events.",
    )
    parser.add_argument(
        "--media-dir",
        help="Directory for media downloaded with --download-media.",
    )
    parser.add_argument("--output", help="JSON output path.")
    parser.add_argument("--session", help="Telethon session path without extension.")
    return parser


def load_config(args):
    config_file = Path(args.config)
    load_env_file(config_file)
    min_text_length = (
        0
        if args.all
        else args.min_text_length
        if args.min_text_length is not None
        else int_env("TELEGRAM_MIN_TEXT_LENGTH", "100")
    )

    api_id = int_env("TELEGRAM_API_ID", required_env("TELEGRAM_API_ID", config_file))
    return ExportConfig(
        api_id=api_id,
        api_hash=required_env("TELEGRAM_API_HASH", config_file),
        chat=args.chat or required_env("TELEGRAM_CHAT", config_file),
        limit=args.limit
        if args.limit is not None
        else int_env("TELEGRAM_ADMIN_LOG_LIMIT", "100000"),
        min_text_length=min_text_length,
        output_file=Path(
            args.output or os.environ.get("TELEGRAM_OUTPUT_FILE", "deleted_messages.json")
        ),
        session=Path(args.session or os.environ.get("TELEGRAM_SESSION", "config/session")),
        config_file=config_file,
        text_only=args.text_only or bool_env("TELEGRAM_TEXT_ONLY"),
        with_links=args.with_links or bool_env("TELEGRAM_WITH_LINKS"),
        download_media=args.download_media or bool_env("TELEGRAM_DOWNLOAD_MEDIA"),
        media_dir=Path(args.media_dir or os.environ.get("TELEGRAM_MEDIA_DIR", "media")),
        incremental=args.incremental or bool_env("TELEGRAM_INCREMENTAL"),
    )


def export_deleted_messages(config):
    try:
        from telethon.errors import ChatAdminRequiredError, ChannelPrivateError, RPCError
        from telethon.sync import TelegramClient
    except ModuleNotFoundError:
        raise SystemExit(
            "Missing dependency: Telethon. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        )

    print("Connecting to Telegram...")

    if config.session.parent != Path("."):
        config.session.parent.mkdir(parents=True, exist_ok=True)
    if config.output_file.parent != Path("."):
        config.output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with TelegramClient(
            str(config.session),
            config.api_id,
            config.api_hash,
        ) as client:
            authorize(client)
            print("Authorization complete.")

            print(f"Getting chat {config.chat}...")
            entity = client.get_entity(config.chat)

            deleted_messages = collect_deleted_messages(
                client,
                entity,
                config,
            )

            exported_messages, added, skipped_duplicates = write_export(
                config,
                deleted_messages,
            )

    except ChatAdminRequiredError:
        raise SystemExit(
            "Error: this Telegram account must be an admin of the target "
            "supergroup or channel."
        )
    except ChannelPrivateError:
        raise SystemExit(
            "Error: chat is not available for this account. Check username, "
            "membership, and admin rights."
        )
    except RPCError as exc:
        raise SystemExit(f"Telegram API error: {type(exc).__name__}: {exc}")

    print(f"Exported deleted messages this run: {len(deleted_messages)}")
    if config.incremental:
        print(f"New messages added: {added}")
        print(f"Duplicates skipped: {skipped_duplicates}")
        print(f"Total messages in file: {len(exported_messages)}")
    print(f"File '{config.output_file}' saved.")


def build_smoke_test_parser():
    parser = argparse.ArgumentParser(
        description="Run a small real Telegram export to verify configuration."
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("TELEGRAM_CONFIG_FILE", str(DEFAULT_CONFIG_FILE)),
        help="Path to env file with Telegram settings.",
    )
    parser.add_argument("--chat", help="Telegram group/channel username or id.")
    parser.add_argument("--session", help="Telethon session path without extension.")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Admin log events limit for the smoke test.",
    )
    parser.add_argument(
        "--output",
        default="deleted_smoke_test.json",
        help="Smoke-test JSON output path.",
    )
    return parser


def smoke_test_main(argv=None):
    args = build_smoke_test_parser().parse_args(argv)
    export_args = build_parser().parse_args(
        [
            "--config",
            args.config,
            "--limit",
            str(args.limit),
            "--all",
            "--with-links",
            "--output",
            args.output,
        ]
    )
    if args.chat:
        export_args.chat = args.chat
    if args.session:
        export_args.session = args.session

    config = load_config(export_args)
    config = replace(
        config,
        download_media=False,
        incremental=False,
        min_text_length=0,
        with_links=True,
    )
    export_deleted_messages(config)


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args)
    export_deleted_messages(config)


if __name__ == "__main__":
    main()

import argparse
import sys
from pathlib import Path

from telegram_deleted_messages.export import (
    DEFAULT_CONFIG_FILE,
    build_parser as build_export_parser,
    load_config,
)


def status_line(ok, label, detail):
    marker = "OK" if ok else "FAIL"
    print(f"[{marker}] {label}: {detail}")


def session_file_for(session_path):
    if session_path.suffix == ".session":
        return session_path
    return session_path.with_suffix(".session")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Check local setup for Telegram deleted-message exports."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_FILE),
        help="Path to env file with Telegram settings.",
    )
    parser.add_argument("--chat", help="Override Telegram group/channel username or id.")
    parser.add_argument("--session", help="Override Telethon session path.")
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Also connect to Telegram and verify authorization/chat access.",
    )
    return parser


def check_telethon():
    try:
        import telethon
    except ModuleNotFoundError:
        status_line(False, "Telethon", "not installed")
        return False, None

    status_line(True, "Telethon", telethon.__version__)
    return True, telethon.__version__


def load_checked_config(args):
    export_parser = build_export_parser()
    export_args = export_parser.parse_args(["--config", args.config])
    if args.chat:
        export_args.chat = args.chat
    if args.session:
        export_args.session = args.session
    return load_config(export_args)


def check_local_setup(args):
    ok = True
    config_file = Path(args.config)

    status_line(True, "Python", sys.version.split()[0])
    telethon_ok, _ = check_telethon()
    ok = ok and telethon_ok

    config_exists = config_file.exists()
    status_line(config_exists, "Config file", str(config_file))
    ok = ok and config_exists

    try:
        config = load_checked_config(args)
    except SystemExit as exc:
        status_line(False, "Config values", str(exc))
        return False, None

    status_line(True, "API ID", "set")
    status_line(True, "API hash", "set")
    status_line(True, "Chat", config.chat)
    status_line(True, "Output", str(config.output_file))
    status_line(True, "Media dir", str(config.media_dir))

    session_file = session_file_for(config.session)
    session_exists = session_file.exists()
    status_line(session_exists, "Session file", str(session_file))
    ok = ok and session_exists

    return ok, config


def check_connection(config):
    try:
        from telethon.errors import ChannelPrivateError, RPCError
        from telethon.sync import TelegramClient
    except ModuleNotFoundError:
        status_line(False, "Connection", "Telethon is not installed")
        return False

    try:
        with TelegramClient(
            str(config.session),
            config.api_id,
            config.api_hash,
        ) as client:
            authorized = client.is_user_authorized()
            status_line(authorized, "Authorization", "saved session authorized")
            if not authorized:
                return False

            entity = client.get_entity(config.chat)
            status_line(True, "Chat access", getattr(entity, "title", config.chat))
            return True
    except ChannelPrivateError:
        status_line(False, "Chat access", "chat is private or unavailable")
    except RPCError as exc:
        status_line(False, "Telegram API", f"{type(exc).__name__}: {exc}")

    return False


def main(argv=None):
    args = build_parser().parse_args(argv)
    ok, config = check_local_setup(args)
    if args.connect and config is not None:
        ok = check_connection(config) and ok

    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

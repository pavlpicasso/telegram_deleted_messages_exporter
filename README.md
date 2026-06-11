# Telegram Deleted Messages Exporter

Exports deleted Telegram messages available in a group or channel admin log.
The Telegram account must have access to the target chat admin log.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Create `config/secrets.env` from `config/secrets.env.example` and fill in:

```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_CHAT=@your_group_or_channel
```

Get `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from Telegram's official app
management page:

1. Open <https://my.telegram.org/apps>.
2. Log in with the phone number connected to your Telegram account.
3. Open **API development tools** and create an app if you do not have one yet.
4. Copy `api_id` to `TELEGRAM_API_ID` and `api_hash` to `TELEGRAM_API_HASH`.

Do not commit `config/secrets.env`; it contains account-specific credentials.

`config/secrets.env`, Telegram sessions, JSON exports, IDE files, caches, and
build outputs are ignored by git.

## Run

```powershell
.\.venv\Scripts\python -m telegram_deleted_messages.export
.\.venv\Scripts\python -m telegram_deleted_messages.formatter --source deleted_messages.json
```

Useful export flags:

```powershell
telegram-deleted-export --all --with-links
telegram-deleted-export --text-only --min-text-length 20
telegram-deleted-export --all --download-media --media-dir media
telegram-deleted-export --incremental --all --with-links
telegram-deleted-export --sender-id 123456789 --deleted-by 987654321
telegram-deleted-export --has-media
telegram-deleted-export --has-links --with-links
```

`--all` sets the minimum text length to `0`. `--text-only` skips media-only
messages. `--with-links` adds extracted links to each JSON item.
`--download-media` saves available media files and writes their paths to JSON.
`--incremental` merges with the existing output file and skips duplicate
`delete_event_id` values.
`--sender-id`, `--deleted-by`, `--has-media`, and `--has-links` filter the
deleted messages that are exported.

## Diagnostics

Check local dependencies, config, and session file:

```powershell
telegram-deleted-doctor
```

Also verify saved Telegram authorization and chat access:

```powershell
telegram-deleted-doctor --connect
```

Run a small real export with safe defaults:

```powershell
telegram-deleted-smoke-test
```

The smoke test uses `--limit 20`, `--all`, `--with-links`, writes
`deleted_smoke_test.json`, and does not download media.

After editable install, the same tools are available as console commands:

```powershell
.\.venv\Scripts\python -m pip install -e .
telegram-deleted-export
telegram-format-messages --source deleted_messages.json
```

## Tests

```powershell
.\.venv\Scripts\python -m unittest discover
```

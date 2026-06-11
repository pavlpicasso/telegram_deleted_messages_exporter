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
```

`--all` sets the minimum text length to `0`. `--text-only` skips media-only
messages. `--with-links` adds extracted links to each JSON item.
`--download-media` saves available media files and writes their paths to JSON.

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

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

By default, export files include the chat name, for example
`your_group_or_channel_admin_log.json`. Use `--output` to override it.

Useful export flags:

```powershell
telegram-admin-log-export --all --with-links
telegram-admin-log-export --events edit --all --with-links
telegram-admin-log-export --events delete,edit --all --resolve-users
telegram-admin-log-export --text-only --min-text-length 20
telegram-admin-log-export --all --download-media --media-dir media
telegram-admin-log-export --incremental --all --with-links
telegram-admin-log-export --checkpoint --incremental --events delete,edit --all
telegram-admin-log-export --sender-id 123456789 --deleted-by 987654321
telegram-admin-log-export --has-media
telegram-admin-log-export --has-links --with-links
telegram-admin-log-export --all --with-links --sort-by message-date
telegram-admin-log-export --all --resolve-users
```

Full export example:

```powershell
telegram-admin-log-export `
  --config config/secrets.env `
  --chat @your_group_or_channel `
  --session config/session `
  --events delete,edit `
  --all `
  --with-links `
  --resolve-users `
  --incremental `
  --checkpoint `
  --sort-by message-date `
  --sort-order asc `
  --output your_group_or_channel_admin_log.json
```

Format an existing JSON export:

```powershell
telegram-format-messages --source your_group_or_channel_admin_log.json --format txt
telegram-format-messages --source your_group_or_channel_admin_log.json --format md --output report.md
telegram-format-messages --source your_group_or_channel_admin_log.json --format html --output report.html
```

Markdown and HTML reports include delete/edit metadata, resolved users when
present, links, and edit diffs.

`--all` sets the minimum text length to `0`. `--text-only` skips media-only
messages. `--with-links` adds extracted links to each JSON item.
`--events delete`, `--events edit`, and `--events delete,edit` choose which
admin-log message events to export. Edit records include `prev_text`,
`new_text`, and a unified `text_diff`.
`--download-media` saves available media files and writes their paths to JSON.
`--incremental` merges with the existing output file and skips duplicate
`delete_event_id` values.
`--checkpoint` stores the last processed admin-log `event_id` in an ignored
state file and resumes from it on the next run.
`--sender-id`, `--deleted-by`, `--has-media`, and `--has-links` filter the
message events that are exported. For edit events, `--deleted-by` matches the
admin-log actor that edited the message.
`--sort-by message-date` writes the JSON in original message date order.
`--resolve-users` adds current names and Telegram usernames for message senders
and deleters when Telegram can resolve those ids. Resolved user objects include
`name`, `display_name`, `username`, and `nick` fields; `nick` is stored with the
leading `@`.

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
telegram-admin-log-export
telegram-deleted-export
telegram-format-messages --source deleted_messages.json
```

`telegram-deleted-export` remains as a compatibility alias.

## Tests

```powershell
.\.venv\Scripts\python -m unittest discover
```

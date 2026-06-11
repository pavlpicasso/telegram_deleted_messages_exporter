# Roadmap

## Done

- Package structure with console commands.
- Local secret config through `config/secrets.env`.
- Git ignore rules for secrets, Telegram sessions, exports, caches, IDE files, and build artifacts.
- Deleted-message export from Telegram admin log.
- Text length, text-only, links, media, sender, deleter, and incremental export options.
- Media download support for available deleted-message media.
- Smoke-test and diagnostics commands.
- Unit tests for config loading, formatting, filtering, incremental merge, smoke-test setup, and diagnostics helpers.

## Next

- Add edited-message export with `ChannelAdminLogEventActionEditMessage`.
- Add `event_type` to exported records, for example `delete` and `edit`.
- Store edited messages with previous and new text:
  - `prev_text`
  - `new_text`
  - `prev_links`
  - `new_links`
  - optional text diff
- Consider renaming or adding a broader command:
  - keep `telegram-deleted-export` for compatibility
  - add `telegram-admin-log-export` for delete/edit/admin-log events
- Add event selection:
  - `--events delete`
  - `--events edit`
  - `--events delete,edit`

## Regular Collection

- Add checkpoint/resume support to avoid scanning the same admin-log window every run.
- Store the last processed admin-log event id in a local ignored state file.
- Add an append-friendly output mode, likely JSONL.
- Document Windows Task Scheduler setup for running the exporter every 30-60 minutes.

## More Filters

- `--contains` for text search.
- `--case-sensitive` for text search.
- `--event-id-min` / `--event-id-max` if admin-log id filtering proves useful.
- `--message-id` for investigating one message.

## Export Formats

- JSONL for large incremental exports.
- CSV for spreadsheet review.
- Markdown or HTML reports for human-readable archives.

## Reliability

- Replace `print()` with structured logging.
- Add `--verbose`, `--quiet`, and `--log-file`.
- Add retry/backoff around Telegram API calls where safe.
- Add clearer error messages for missing admin rights and expired/invalid sessions.

## Security

- Rotate the Telegram API credentials that were previously present in local code.
- Add a pre-commit secret scan option or documented manual check before public pushes.
- Keep `config/secrets.env`, `*.session`, exports, and downloaded media out of git.

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
- Delete/edit event selection with `--events`.
- Broader `telegram-admin-log-export` command name with `telegram-deleted-export` compatibility alias.
- Unified text diff for edited messages.
- Checkpoint/resume support with the last processed admin-log event id.

## Regular Collection

- Add an append-friendly output mode, likely JSONL.
- Document Windows Task Scheduler setup for running the exporter every 30-60 minutes.

## Export Formats

- JSONL for large incremental exports.
- CSV for spreadsheet review.
- Markdown or HTML reports for human-readable archives.

## Security

- Add a pre-commit secret scan option or documented manual check before public pushes.
- Keep `config/secrets.env`, `*.session`, exports, and downloaded media out of git.

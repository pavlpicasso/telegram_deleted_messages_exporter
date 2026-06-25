import argparse
import html
import json
from pathlib import Path


DEFAULT_SOURCE_FILE = Path("deleted_messages.json")
DEFAULT_OUTPUT_FILES = {
    "txt": Path("telegram_messages.txt"),
    "md": Path("telegram_messages.md"),
    "html": Path("telegram_messages.html"),
}
DEFAULT_MAX_TELEGRAM_LENGTH = 3900


def format_links(links):
    if not links:
        return ""

    lines = ["", "Links:"]
    for link in links:
        text = (link.get("text") or "").strip()
        url = (link.get("url") or "").strip()
        if not url:
            continue
        if text and text != url:
            lines.append(f"- {text}: {url}")
        else:
            lines.append(f"- {url}")

    return "\n".join(lines) if len(lines) > 2 else ""


def split_text(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        chunk = text[:limit]
        split_points = [chunk.rfind("\n\n"), chunk.rfind("\n")]
        sentence_at = chunk.rfind(". ")
        if sentence_at != -1:
            split_points.append(sentence_at + 1)

        split_at = max(split_points)
        if split_at < limit // 2:
            split_at = limit

        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    return chunks


def build_blocks(messages, max_length=DEFAULT_MAX_TELEGRAM_LENGTH):
    blocks = []

    for index, message in enumerate(messages, start=1):
        text = (message.get("text") or "").strip()
        links_text = format_links(message.get("links") or [])
        meta = (
            f"[{index}] Deleted: {message.get('deleted_at', '')}\n"
            f"Message date: {message.get('message_date', '')}\n"
            f"Message ID: {message.get('message_id', '')}\n"
        )

        reserved = len(meta) + len(links_text) + 80
        text_limit = max(1000, max_length - reserved)
        chunks = split_text(text, text_limit)

        for part_index, chunk in enumerate(chunks, start=1):
            part_suffix = (
                f" / part {part_index} of {len(chunks)}" if len(chunks) > 1 else ""
            )
            block = (
                f"[{index}{part_suffix}]\n"
                f"Deleted: {message.get('deleted_at', '')}\n"
                f"Message date: {message.get('message_date', '')}\n\n"
                f"{chunk}"
            )
            if part_index == len(chunks) and links_text:
                block += f"\n{links_text}"
            blocks.append(block.strip())

    return blocks


def load_messages(source_file):
    data = json.loads(source_file.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"]
    raise SystemExit(f"Invalid source file: {source_file}")


def user_label(summary, fallback_id=None):
    if not summary:
        return str(fallback_id or "")

    username = summary.get("username")
    nick = summary.get("nick") or (f"@{username}" if username else None)
    display_name = summary.get("display_name") or summary.get("name")
    entity_id = summary.get("id") or fallback_id

    if display_name and nick:
        label = f"{display_name} {nick}"
    elif nick:
        label = nick
    elif display_name:
        label = display_name
    else:
        label = str(entity_id or "")

    if label and entity_id and label != str(entity_id):
        return f"{label} ({entity_id})"
    return label


def markdown_escape(text):
    return str(text).replace("\\", "\\\\").replace("`", "\\`")


def markdown_links(links):
    lines = []
    for link in links or []:
        text = (link.get("text") or link.get("url") or "").strip()
        url = (link.get("url") or "").strip()
        if not url:
            continue
        lines.append(f"- [{markdown_escape(text)}]({url})")
    return lines


def build_markdown(messages):
    lines = ["# Telegram Admin Log Export", ""]
    for index, message in enumerate(messages, start=1):
        event_type = message.get("event_type") or "delete"
        lines.extend(
            [
                f"## {index}. {event_type.upper()} message {message.get('message_id', '')}",
                "",
                f"- Event ID: `{message.get('event_id') or message.get('delete_event_id', '')}`",
                f"- Message date: `{message.get('message_date', '')}`",
                f"- Event date: `{message.get('event_at') or message.get('deleted_at') or message.get('edited_at') or ''}`",
                f"- Sender: {markdown_escape(user_label(message.get('sender'), message.get('sender_id')))}",
                f"- Actor: {markdown_escape(user_label(message.get('actor'), message.get('actor_id') or message.get('deleted_by') or message.get('edited_by')))}",
                "",
            ]
        )

        if event_type == "edit":
            lines.extend(
                [
                    "### Previous text",
                    "",
                    "```text",
                    message.get("prev_text", ""),
                    "```",
                    "",
                    "### New text",
                    "",
                    "```text",
                    message.get("new_text", ""),
                    "```",
                    "",
                ]
            )
            diff_lines = (message.get("text_diff") or {}).get("lines") or []
            if diff_lines:
                lines.extend(["### Diff", "", "```diff", *diff_lines, "```", ""])
        else:
            lines.extend(
                [
                    "```text",
                    message.get("text", ""),
                    "```",
                    "",
                ]
            )

        links = markdown_links(message.get("links") or message.get("new_links") or [])
        if links:
            lines.extend(["### Links", "", *links, ""])

    return "\n".join(lines).rstrip() + "\n"


def html_links(links):
    items = []
    for link in links or []:
        text = (link.get("text") or link.get("url") or "").strip()
        url = (link.get("url") or "").strip()
        if not url:
            continue
        items.append(
            f'<li><a href="{html.escape(url, quote=True)}">{html.escape(text)}</a></li>'
        )
    return f"<ul>{''.join(items)}</ul>" if items else ""


def html_sender_key(message):
    sender = message.get("sender") or {}
    return str(sender.get("id") or message.get("sender_id") or "unknown")


def html_event_label(message):
    event_type = (message.get("event_type") or "delete").upper()
    message_id = str(message.get("message_id", ""))
    return f"{event_type} #{message_id}"


def html_compact_meta(message):
    event_date = (
        message.get("event_at") or message.get("deleted_at") or message.get("edited_at") or ""
    )
    actor_id = message.get("actor_id") or message.get("deleted_by") or message.get("edited_by")
    actor = user_label(message.get("actor"), actor_id)
    pieces = [
        f"message: {message.get('message_date', '')}",
        f"event: {event_date}",
        f"actor: {actor}",
        f"event id: {message.get('event_id') or message.get('delete_event_id') or ''}",
    ]
    return " | ".join(html.escape(str(piece)) for piece in pieces if piece)


def html_message_body(message):
    event_type = message.get("event_type") or "delete"
    if event_type == "edit":
        new_text = html.escape(message.get("new_text") or message.get("text") or "")
        prev_text = html.escape(message.get("prev_text", ""))
        diff_lines = "\n".join((message.get("text_diff") or {}).get("lines") or [])
        diff_html = html.escape(diff_lines)
        return "\n".join(
            [
                f'<div class="text">{new_text}</div>',
                "<details>",
                "<summary>Previous text and diff</summary>",
                f'<pre class="previous">{prev_text}</pre>',
                f'<pre class="diff">{diff_html}</pre>' if diff_html else "",
                "</details>",
            ]
        )
    return f'<div class="text">{html.escape(message.get("text", ""))}</div>'


def build_html(messages):
    sender_classes = {}
    next_color = 0
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Telegram Admin Log Export</title>",
        "<style>",
        "body{margin:0;font-family:Arial,sans-serif;background:#f2f2f2;color:#202124}",
        "#chat{max-width:920px;margin:0 auto;padding:18px}",
        "h1{font-size:20px;margin:0 0 16px}",
        ".message{margin-bottom:10px;padding:9px 12px;border-radius:10px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1);border-left:5px solid #999}",
        ".top{display:flex;gap:8px;align-items:baseline;justify-content:space-between;flex-wrap:wrap;margin-bottom:3px}",
        ".sender{font-weight:700;font-size:14px;min-width:0;word-break:break-word}",
        ".badge{font-size:11px;color:#fff;background:#666;border-radius:999px;padding:2px 7px;white-space:nowrap}",
        ".meta{color:#666;font-size:11px;margin-bottom:7px}",
        ".text{white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.38}",
        "details{margin-top:8px}",
        "summary{cursor:pointer;color:#555;font-size:12px}",
        "pre{white-space:pre-wrap;word-break:break-word;background:#f6f8fa;padding:8px;border-radius:6px;overflow:auto;font-size:12px}",
        ".previous{background:#fafafa}",
        ".diff{background:#fff8e1}",
        ".links{margin-top:6px;font-size:12px}",
        ".links ul{margin:4px 0 0 18px;padding:0}",
        ".color0{border-left-color:#4caf50}.color1{border-left-color:#2196f3}.color2{border-left-color:#ff9800}.color3{border-left-color:#9c27b0}",
        ".color4{border-left-color:#009688}.color5{border-left-color:#f44336}.color6{border-left-color:#607d8b}.color7{border-left-color:#795548}",
        "</style>",
        "</head>",
        "<body>",
        '<main id="chat">',
        "<h1>Telegram Admin Log Export</h1>",
    ]

    for message in messages:
        sender_key = html_sender_key(message)
        if sender_key not in sender_classes:
            sender_classes[sender_key] = f"color{next_color % 8}"
            next_color += 1
        sender = html.escape(user_label(message.get("sender"), message.get("sender_id")))
        links = html_links(message.get("links") or message.get("new_links") or [])
        links_html = f'<div class="links">{links}</div>' if links else ""
        parts.extend(
            [
                f'<article class="message {sender_classes[sender_key]}">',
                '<div class="top">',
                f'<div class="sender">{sender}</div>',
                f'<div class="badge">{html.escape(html_event_label(message))}</div>',
                "</div>",
                f'<div class="meta">{html_compact_meta(message)}</div>',
                html_message_body(message),
                links_html,
                "</article>",
            ]
        )

    parts.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(parts)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Convert exported Telegram admin-log JSON to text, Markdown, or HTML."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE_FILE),
        help="Input JSON file produced by telegram-admin-log-export.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output text file.",
    )
    parser.add_argument(
        "--format",
        choices=["txt", "md", "html"],
        default="txt",
        help="Output format.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_MAX_TELEGRAM_LENGTH,
        help="Maximum Telegram message length to target.",
    )
    return parser


def convert_messages(source_file, output_file, max_length, output_format="txt"):
    messages = load_messages(source_file)

    if output_format == "txt":
        blocks = build_blocks(messages, max_length=max_length)
        output = []
        for index, block in enumerate(blocks, start=1):
            output.append(f"===== TELEGRAM MESSAGE {index:02d} =====\n{block}")
        content = "\n\n".join(output) + "\n"
        print(f"Telegram blocks written: {len(blocks)}")
    elif output_format == "md":
        content = build_markdown(messages)
    elif output_format == "html":
        content = build_html(messages)
    else:
        raise SystemExit(f"Invalid output format: {output_format}")

    output_file.write_text(content, encoding="utf-8")
    print(f"Messages read: {len(messages)}")
    print(f"Output file: {output_file}")


def main(argv=None):
    args = build_parser().parse_args(argv)
    output_file = Path(args.output) if args.output else DEFAULT_OUTPUT_FILES[args.format]
    convert_messages(Path(args.source), output_file, args.max_length, args.format)


if __name__ == "__main__":
    main()

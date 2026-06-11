import argparse
import json
from pathlib import Path


DEFAULT_SOURCE_FILE = Path("deleted_messages.json")
DEFAULT_OUTPUT_FILE = Path("telegram_messages.txt")
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


def build_parser():
    parser = argparse.ArgumentParser(
        description="Convert exported deleted messages JSON to Telegram-sized text."
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE_FILE),
        help="Input JSON file produced by telegram-deleted-export.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_FILE),
        help="Output text file.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_MAX_TELEGRAM_LENGTH,
        help="Maximum Telegram message length to target.",
    )
    return parser


def convert_messages(source_file, output_file, max_length):
    messages = json.loads(source_file.read_text(encoding="utf-8"))
    blocks = build_blocks(messages, max_length=max_length)

    output = []
    for index, block in enumerate(blocks, start=1):
        output.append(f"===== TELEGRAM MESSAGE {index:02d} =====\n{block}")

    output_file.write_text("\n\n".join(output) + "\n", encoding="utf-8")
    print(f"Messages read: {len(messages)}")
    print(f"Telegram blocks written: {len(blocks)}")
    print(f"Output file: {output_file}")


def main(argv=None):
    args = build_parser().parse_args(argv)
    convert_messages(Path(args.source), Path(args.output), args.max_length)


if __name__ == "__main__":
    main()

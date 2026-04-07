#!/usr/bin/env python3
"""Write a captured web article payload to a timestamp-title archive folder."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any


INVALID_SEGMENT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")


def sanitize_segment(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip()
    text = INVALID_SEGMENT_CHARS.sub("-", text)
    text = WHITESPACE.sub(" ", text)
    text = text.strip(" .-_")
    return text or "untitled"


def choose_extension(data_url: str, provided_name: str) -> str:
    suffix = Path(provided_name or "").suffix
    if suffix:
        return suffix.lower()

    match = re.match(r"data:([^;,]+)", data_url)
    if not match:
        return ".bin"
    mime = match.group(1).lower()
    guessed = mimetypes.guess_extension(mime)
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ".bin"


def decode_data_url(data_url: str) -> bytes:
    prefix, encoded = data_url.split(",", 1)
    if ";base64" not in prefix:
        raise ValueError("Only base64 data URLs are supported")
    return base64.b64decode(encoded)


def load_payload(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    return payload


def build_header(payload: dict[str, Any]) -> str:
    lines = [f"# {payload.get('title') or 'Untitled'}", ""]
    lines.append(f"- Source: {payload.get('source_url') or ''}")
    lines.append(f"- Captured: {payload.get('captured_at') or datetime.now().astimezone().isoformat()}")
    if payload.get("author"):
        lines.append(f"- Author: {payload['author']}")
    if payload.get("published_at"):
        lines.append(f"- Published: {payload['published_at']}")
    return "\n".join(lines).rstrip()


def build_markdown_filename(archive_dir: Path) -> str:
    return f"{archive_dir.name}.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Existing parent directory for the archive")
    parser.add_argument("--json", default="-", help="Path to the JSON payload, or - for stdin")
    parser.add_argument(
        "--timestamp",
        help="Override folder timestamp in YYYYMMDD-HHMMSS format for testing",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    if not output_dir.exists() or not output_dir.is_dir():
        raise SystemExit(f"Output directory does not exist or is not a directory: {output_dir}")

    payload = load_payload(args.json)
    body = payload.get("body_markdown") or payload.get("markdown") or ""
    if not isinstance(body, str) or not body.strip():
        raise SystemExit("Payload is missing non-empty body_markdown/markdown")

    title = sanitize_segment(str(payload.get("title") or "untitled"))
    timestamp = args.timestamp or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    archive_dir = output_dir / f"{timestamp}-{title}"
    archive_dir.mkdir(parents=False, exist_ok=False)

    images_dir = archive_dir / "images"
    images_dir.mkdir()

    replacements: list[tuple[str, str]] = []
    for index, image in enumerate(payload.get("images") or [], start=1):
        if not isinstance(image, dict):
            continue
        data_url = image.get("data_url")
        if not isinstance(data_url, str) or not data_url.startswith("data:"):
            continue
        extension = choose_extension(data_url, str(image.get("filename") or ""))
        base_name = sanitize_segment(Path(str(image.get("filename") or f"image-{index:02d}")).stem)
        file_name = f"{index:02d}-{base_name}{extension}"
        image_path = images_dir / file_name
        image_path.write_bytes(decode_data_url(data_url))

        alt = str(image.get("alt") or "").strip()
        label = alt or image_path.stem
        markdown_ref = f"![{label}](images/{image_path.name})"
        placeholder = str(image.get("placeholder") or "").strip()
        if placeholder:
            replacements.append((placeholder, markdown_ref))
        else:
            body += f"\n\n{markdown_ref}"

    for placeholder, markdown_ref in replacements:
        body = body.replace(placeholder, markdown_ref)

    markdown = f"{build_header(payload)}\n\n{body.strip()}\n"
    markdown_path = archive_dir / build_markdown_filename(archive_dir)
    markdown_path.write_text(markdown, encoding="utf-8")

    print(str(archive_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

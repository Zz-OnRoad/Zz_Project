"""Build a structural Markdown handoff from Docling DOCX JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from docling_core.types.doc import DoclingDocument, ImageRefMode


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(value: str) -> str:
    value = CONTROL_CHARS.sub("", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docling-json", required=True, type=Path)
    parser.add_argument("--source-docx", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    if args.source_docx.suffix.lower() != ".docx":
        raise ValueError("Only DOCX sources are supported by this builder.")

    document = DoclingDocument.load_from_json(args.docling_json)
    body = clean(
        document.export_to_markdown(
            image_mode=ImageRefMode.PLACEHOLDER,
            traverse_pictures=True,
        )
    )
    if not body:
        body = "（未抽取到正文文字。）"

    raw_document = json.loads(args.docling_json.read_text(encoding="utf-8"))
    image_count = len(raw_document.get("pictures", []))
    table_count = len(raw_document.get("tables", []))

    lines = [
        "---",
        "schema_version: 1",
        f"title: {json.dumps(args.title, ensure_ascii=False)}",
        f"source_file: {json.dumps(args.source_docx.as_posix(), ensure_ascii=False)}",
        "source_type: docx",
        'scope: "full_document"',
        f"generated_on: {date.today().isoformat()}",
        "handoff_format: markdown",
        "pagination: not_inferred",
        "content_status: source_extraction_not_editorial_rewrite",
        f"source_sha256: {file_sha256(args.source_docx)}",
        "---",
        "",
        f"# {args.title}",
        "",
        "## 转换说明",
        "",
        "正文由 Docling 直接解析 DOCX 后输出，不经过 PDF 中转，也不推断物理页码。",
        "",
        f"- 抽取到的独立图片资源：{image_count}",
        f"- 抽取到的表格结构：{table_count}",
        "",
        "## 抽取正文",
        "",
        body,
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

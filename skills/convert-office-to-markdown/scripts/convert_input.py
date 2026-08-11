"""Convert every PPTX and DOCX in input/ into one Markdown handoff.

The conversion is deterministic and offline. Office parsing is delegated to
the project's validated Docling entry point and builders; no LLM is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from docling_core.types.doc import DoclingDocument, ImageRefMode


SUPPORTED_SUFFIXES = {".pptx", ".docx"}
EXPLICITLY_REJECTED_SUFFIXES = {".pdf", ".ppt", ".doc"}
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
IMAGE_PLACEHOLDER = re.compile(r"(?m)^\s*<!-- image -->\s*$")


@dataclass(frozen=True)
class ConvertedSource:
    source: Path
    source_hash: str
    source_type: str
    conversion_mode: str
    markdown: str
    warnings: tuple[str, ...]


def project_root() -> Path:
    """Use the caller's working directory as the conversion project root."""

    return Path.cwd().resolve()


def resolve_argument(value: Path, root: Path) -> Path:
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def clean(value: str) -> str:
    value = CONTROL_CHARS.sub("", value)
    value = IMAGE_PLACEHOLDER.sub("", value)
    value = re.sub(r"(?m)^[ \t]+$", "", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def strip_front_matter(markdown: str) -> str:
    normalized = markdown.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return normalized.strip()
    closing = normalized.find("\n---\n", 4)
    if closing == -1:
        return normalized.strip()
    return normalized[closing + 5 :].strip()


def run_checked(command: list[str], root: Path) -> None:
    environment = os.environ.copy()
    environment["HF_HUB_OFFLINE"] = "1"
    environment["TRANSFORMERS_OFFLINE"] = "1"
    result = subprocess.run(
        command,
        cwd=root,
        env=environment,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or f"Command failed with exit code {result.returncode}")


def discover_sources(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(
            f"Input directory does not exist: {input_dir}. "
            "Create it and add PPTX or DOCX files."
        )

    rejected: list[Path] = []
    supported: list[Path] = []
    for path in input_dir.rglob("*"):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_SUFFIXES:
            supported.append(path)
        elif suffix in EXPLICITLY_REJECTED_SUFFIXES:
            rejected.append(path)

    if rejected:
        names = ", ".join(str(path.relative_to(input_dir)) for path in rejected)
        raise ValueError(
            "Unsupported input detected. This Skill accepts only PPTX and DOCX: "
            f"{names}"
        )
    if not supported:
        raise ValueError(
            f"No PPTX or DOCX files found in {input_dir}. "
            "Add source files before running the Skill."
        )
    return sorted(
        supported,
        key=lambda path: path.relative_to(input_dir).as_posix().casefold(),
    )


def page_image_counts(raw_document: dict, page_count: int) -> dict[int, int]:
    counts = {page_no: 0 for page_no in range(1, page_count + 1)}
    for picture in raw_document.get("pictures", []):
        pages = {
            prov.get("page_no")
            for prov in picture.get("prov", [])
            if isinstance(prov.get("page_no"), int)
        }
        for page_no in pages:
            if page_no in counts:
                counts[page_no] += 1
    return counts


def build_generic_ppt_markdown(json_path: Path, source: Path) -> str:
    raw_document = json.loads(json_path.read_text(encoding="utf-8"))
    document = DoclingDocument.load_from_json(json_path)
    page_count = len(document.pages)
    image_counts = page_image_counts(raw_document, page_count)

    lines = [
        f"# {source.stem}",
        "",
        "## 转换说明",
        "",
        "本文件按 PPTX 的结构化页面顺序抽取，未进行逐页视觉阅读顺序校正。",
        "普通图片不做画面语义分析，仅保留数量占位。",
    ]
    for page_no in range(1, page_count + 1):
        body = clean(
            document.export_to_markdown(
                page_no=page_no,
                image_mode=ImageRefMode.PLACEHOLDER,
                traverse_pictures=True,
            )
        )
        if not body:
            body = "（本页未抽取到可见正文文字。）"
        count = image_counts[page_no]
        status = "有" if count else "无"
        lines.extend(
            [
                "",
                "---",
                "",
                f"## 幻灯片 {page_no}",
                "",
                "### 抽取文字",
                "",
                body,
                "",
                "### 图片占位",
                "",
                f"[图片占位：{status}，共 {count} 张]",
            ]
        )
    return "\n".join(lines).strip()


def convert_source(source: Path, work_dir: Path, root: Path) -> ConvertedSource:
    source_hash = file_sha256(source)
    source_work = work_dir / source_hash[:16]
    source_work.mkdir(parents=True, exist_ok=True)
    script_dir = Path(__file__).resolve().parent

    run_checked(
        [
            sys.executable,
            str(script_dir / "convert_office.py"),
            str(source),
            "--output-dir",
            str(source_work),
        ],
        root,
    )
    json_path = source_work / f"{source.stem}.json"
    rendered_path = source_work / "rendered.md"

    if source.suffix.lower() == ".docx":
        run_checked(
            [
                sys.executable,
                str(script_dir / "build_word_markdown.py"),
                "--docling-json",
                str(json_path),
                "--source-docx",
                str(source),
                "--output",
                str(rendered_path),
                "--title",
                source.stem,
            ],
            root,
        )
        markdown = strip_front_matter(rendered_path.read_text(encoding="utf-8"))
        return ConvertedSource(
            source=source,
            source_hash=source_hash,
            source_type="docx",
            conversion_mode="structural_document_order",
            markdown=markdown,
            warnings=(),
        )

    markdown = build_generic_ppt_markdown(json_path, source)
    return ConvertedSource(
        source=source,
        source_hash=source_hash,
        source_type="pptx",
        conversion_mode="generic_structural_page_order",
        markdown=markdown,
        warnings=(
            "PPTX 按结构顺序转换；复杂多栏页面的阅读顺序需要人工复核。",
        ),
    )


def render_combined(
    converted: list[ConvertedSource], input_dir: Path
) -> str:
    lines = [
        "---",
        "schema_version: 1",
        'title: "原始材料转换结果"',
        f"generated_on: {date.today().isoformat()}",
        "handoff_format: markdown",
        "conversion_mode: deterministic_offline_no_llm",
        f"source_count: {len(converted)}",
        "---",
        "",
        "# 原始材料转换结果",
        "",
        "## 转换边界",
        "",
        "- 本文件由本地确定性程序生成，未调用 LLM、外部 API 或云端服务。",
        "- 当前内容是源材料抽取，不包含事实核验、内容分析、改写或逐页策划。",
        "- 普通图片只保留数量占位，不推断图片画面含义。",
        "",
        "## 来源清单",
        "",
        "| 序号 | 类型 | 文件 | SHA-256 | 转换模式 |",
        "|---:|---|---|---|---|",
    ]
    for index, item in enumerate(converted, start=1):
        source_name = item.source.relative_to(input_dir).as_posix()
        lines.append(
            f"| {index} | {item.source_type.upper()} | {source_name} | "
            f"`{item.source_hash}` | `{item.conversion_mode}` |"
        )

    warnings = [
        f"{item.source.name}：{warning}"
        for item in converted
        for warning in item.warnings
    ]
    lines.extend(["", "## 质量提示", ""])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- 当前全部来源均使用已验证或结构稳定的转换路径。")

    for index, item in enumerate(converted, start=1):
        lines.extend(
            [
                "",
                "---",
                "",
                f"# 来源 {index}：{item.source.name}",
                "",
                item.markdown,
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 下游使用约束",
            "",
            "- 将本文件作为内容审计层的唯一转换输入。",
            "- 对标记为通用结构顺序的 PPTX，先复核复杂页面的阅读顺序。",
            "- 如图片包含决定性文字，另行执行本地 OCR 并人工复核。",
            "- 不得把图片占位、推测或未经核验的 OCR 结果当作已确认事实。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="Convert PPTX and DOCX files into one offline Markdown file."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("input"))
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("output") / "converted-content.md",
    )
    args = parser.parse_args()

    input_dir = resolve_argument(args.input_dir, root)
    output_file = resolve_argument(args.output_file, root)
    sources = discover_sources(input_dir)

    with tempfile.TemporaryDirectory(prefix=".office-md-", dir=root) as temporary:
        work_dir = Path(temporary)
        converted = [
            convert_source(source=source, work_dir=work_dir, root=root)
            for source in sources
        ]
        combined = render_combined(converted, input_dir)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_file.with_name(f".{output_file.name}.tmp")
    temporary_output.write_text(combined, encoding="utf-8")
    temporary_output.replace(output_file)

    warning_count = sum(len(item.warnings) for item in converted)
    print(f"output={output_file}")
    print(f"sources={len(converted)}")
    print("types=" + ",".join(sorted({item.source_type for item in converted})))
    print(f"warnings={warning_count}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from None

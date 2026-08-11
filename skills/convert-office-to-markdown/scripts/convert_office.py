"""Convert a PPTX or DOCX source to referenced-image Docling JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from docling.backend.mspowerpoint_backend import MsPowerpointDocumentBackend
from docling.backend.msword_backend import MsWordDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import InputDocument
from docling_core.types.doc import ImageRefMode


FORMAT_CONFIG = {
    ".pptx": (InputFormat.PPTX, MsPowerpointDocumentBackend),
    ".docx": (InputFormat.DOCX, MsWordDocumentBackend),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    suffix = source.suffix.lower()
    if suffix not in FORMAT_CONFIG:
        supported = ", ".join(sorted(FORMAT_CONFIG))
        raise ValueError(f"Unsupported source type {suffix!r}; expected {supported}.")

    input_format, backend_class = FORMAT_CONFIG[suffix]
    input_document = InputDocument(
        path_or_stream=source,
        format=input_format,
        backend=backend_class,
    )
    if not input_document.valid or not input_document._backend.is_valid():
        raise RuntimeError(f"Unable to load source document: {source}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_json = args.output_dir / f"{source.stem}.json"
    artifacts_dir = args.output_dir / f"{source.stem}_artifacts"

    try:
        document = input_document._backend.convert()
        document.save_as_json(
            output_json,
            artifacts_dir=artifacts_dir,
            image_mode=ImageRefMode.REFERENCED,
        )
    finally:
        input_document._backend.unload()


if __name__ == "__main__":
    main()

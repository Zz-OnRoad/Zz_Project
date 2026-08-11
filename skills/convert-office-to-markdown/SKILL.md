---
name: convert-office-to-markdown
description: Convert all PPTX and DOCX source files in this project's input directory into one offline Markdown handoff. Use when the user asks to run, start, or invoke the Office source conversion stage; refresh the converted source material; or combine newly placed PowerPoint and Word files into a single output. Do not use for PDF, content analysis, rewriting, slide outlining, or HTML generation.
---

# Convert Office to Markdown

Run the project's deterministic Office conversion stage. Do not call an LLM, external API, browser, or network service.

## Execute

1. Treat the current working directory as the conversion project root.
2. Resolve this Skill's directory from the loaded `SKILL.md` location.
3. Confirm `.venv/Scripts/python.exe` exists in the project root. If it does not, create the virtual environment and install this Skill's `requirements.txt` before continuing.
4. Read source files from `input/`. Accept only `.pptx` and `.docx`; ignore Office lock files beginning with `~$`.
5. Run the converter bundled with this Skill:

   ```powershell
   & .\.venv\Scripts\python.exe <skill-directory>\scripts\convert_input.py
   ```

6. Return the generated `output/converted-content.md`, source count, source types, and any quality warnings.

## Conversion rules

- Preserve every input file; never modify or delete source material.
- Generate exactly one consolidated Markdown handoff per run.
- Overwrite only `output/converted-content.md`.
- Reject PDF and legacy `.ppt` / `.doc` inputs with a clear error.
- Use Docling's structural page order for PPTX and mark it as not visually reviewed.
- Preserve Word document structure without inventing physical page numbers.
- Represent ordinary pictures with count placeholders. Do not infer image meaning.
- Do not perform content analysis, fact checking, rewriting, slide planning, or HTML generation.
- Keep conversion offline by setting Hugging Face and Transformers offline flags.

## Failure handling

- If `input/` contains no supported files, stop and ask the user to add PPTX or DOCX files.
- If a source cannot be parsed, do not publish a partial consolidated output.
- If a PPTX has complex multi-column layouts, complete conversion but report that reading order requires human review.
- If image text is essential, report that it requires the separate local OCR review step; do not silently invent or describe image content.

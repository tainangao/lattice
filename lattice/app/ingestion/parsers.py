from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


class ParsingError(Exception):
    pass


@dataclass(frozen=True)
class ParsedSegment:
    page: int
    text: str


def _parse_pdf_bytes(file_bytes: bytes) -> list[ParsedSegment]:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise ParsingError("PyMuPDF is required for PDF ingestion") from exc

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            segments: list[ParsedSegment] = []
            for index, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    segments.append(ParsedSegment(page=index, text=text))
    except Exception as exc:
        raise ParsingError("Unable to parse PDF file") from exc

    return segments


def _parse_docx_bytes(file_bytes: bytes) -> list[ParsedSegment]:
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise ParsingError("python-docx is required for DOCX ingestion") from exc

    try:
        document = Document(BytesIO(file_bytes))
    except Exception as exc:
        raise ParsingError("Unable to parse DOCX file") from exc

    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    text = "\n".join(value for value in paragraphs if value)
    if not text:
        return []
    return [ParsedSegment(page=1, text=text)]


def parse_uploaded_file(content_type: str, file_bytes: bytes) -> list[ParsedSegment]:
    if content_type in {"text/plain", "text/markdown"}:
        text = file_bytes.decode("utf-8", errors="ignore")
        return [ParsedSegment(page=1, text=text)] if text.strip() else []
    if content_type == "application/pdf":
        return _parse_pdf_bytes(file_bytes)
    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        return _parse_docx_bytes(file_bytes)
    raise ParsingError("Unsupported file format. Use PDF, DOCX, MD, or TXT.")

from __future__ import annotations

from io import BytesIO


class ParsingError(Exception):
    pass


def _parse_pdf_bytes(file_bytes: bytes) -> str:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise ParsingError("PyMuPDF is required for PDF ingestion") from exc

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            pages = [page.get_text("text") for page in document]
    except Exception as exc:
        raise ParsingError("Unable to parse PDF file") from exc

    return "\n".join(section.strip() for section in pages if section.strip())


def _parse_docx_bytes(file_bytes: bytes) -> str:
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise ParsingError("python-docx is required for DOCX ingestion") from exc

    try:
        document = Document(BytesIO(file_bytes))
    except Exception as exc:
        raise ParsingError("Unable to parse DOCX file") from exc

    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    return "\n".join(text for text in paragraphs if text)


def parse_uploaded_file(content_type: str, file_bytes: bytes) -> str:
    if content_type in {"text/plain", "text/markdown"}:
        return file_bytes.decode("utf-8", errors="ignore")
    if content_type == "application/pdf":
        return _parse_pdf_bytes(file_bytes)
    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        return _parse_docx_bytes(file_bytes)
    raise ParsingError("Unsupported file format. Use PDF, DOCX, MD, or TXT.")

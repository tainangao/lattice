from __future__ import annotations

import hashlib
from dataclasses import replace
from uuid import uuid4

from lattice.app.ingestion.contracts import (
    ChunkMetadata,
    DocumentChunk,
    IngestionJob,
    INGESTION_STATUS_FAILED,
    INGESTION_STATUS_PROCESSING,
    INGESTION_STATUS_QUEUED,
    INGESTION_STATUS_SUCCESS,
)
from lattice.app.runtime.store import RuntimeStore

SUPPORTED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _chunk_text(
    text: str, chunk_size: int = 400, overlap: int = 80
) -> list[tuple[int, int, str]]:
    chunks: list[tuple[int, int, str]] = []
    if not text.strip():
        return chunks
    cursor = 0
    while cursor < len(text):
        end = min(len(text), cursor + chunk_size)
        snippet = text[cursor:end].strip()
        if snippet:
            chunks.append((cursor, end, snippet))
        if end == len(text):
            break
        cursor = max(0, end - overlap)
    return chunks


def _fake_embedding(content: str) -> tuple[float, ...]:
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    values = [int(byte) / 255.0 for byte in digest[:12]]
    return tuple(values)


def _decode_text_bytes(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")


def create_ingestion_job(
    *,
    store: RuntimeStore,
    user_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> IngestionJob:
    job_id = f"ing-{uuid4().hex[:12]}"
    initial = IngestionJob(
        job_id=job_id,
        status=INGESTION_STATUS_QUEUED,
        filename=filename,
        content_type=content_type,
        user_id=user_id,
        chunk_count=0,
        error_message=None,
    )
    store.ingestion_jobs[job_id] = initial
    processing = replace(initial, status=INGESTION_STATUS_PROCESSING)
    store.ingestion_jobs[job_id] = processing

    if content_type not in SUPPORTED_CONTENT_TYPES:
        failed = replace(
            processing,
            status=INGESTION_STATUS_FAILED,
            error_message="Unsupported file format. Use PDF, DOCX, MD, or TXT.",
        )
        store.ingestion_jobs[job_id] = failed
        return failed

    if content_type in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        failed = replace(
            processing,
            status=INGESTION_STATUS_FAILED,
            error_message=(
                "Parser not wired yet for this file type in the rebuild branch. "
                "TXT/MD ingest is available now."
            ),
        )
        store.ingestion_jobs[job_id] = failed
        return failed

    parsed_text = _decode_text_bytes(file_bytes)
    chunk_rows = _chunk_text(parsed_text)
    chunks: list[DocumentChunk] = []
    for index, (offset_start, offset_end, content) in enumerate(chunk_rows, start=1):
        chunk_id = f"{job_id}-chunk-{index}"
        metadata = ChunkMetadata(
            source=filename,
            page=1,
            offset_start=offset_start,
            offset_end=offset_end,
            user_id=user_id,
        )
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                content=content,
                metadata=metadata,
                embedding=_fake_embedding(content),
            )
        )

    existing = store.private_chunks_by_user.setdefault(user_id, [])
    existing.extend(chunks)

    completed = replace(
        processing,
        status=INGESTION_STATUS_SUCCESS,
        chunk_count=len(chunks),
        error_message=None,
    )
    store.ingestion_jobs[job_id] = completed
    return completed


def list_user_ingestion_jobs(
    *, store: RuntimeStore, user_id: str
) -> list[IngestionJob]:
    jobs = [job for job in store.ingestion_jobs.values() if job.user_id == user_id]
    return sorted(jobs, key=lambda job: job.job_id, reverse=True)


def get_user_ingestion_job(
    *,
    store: RuntimeStore,
    user_id: str,
    job_id: str,
) -> IngestionJob | None:
    job = store.ingestion_jobs.get(job_id)
    if not job or job.user_id != user_id:
        return None
    return job

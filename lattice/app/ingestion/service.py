from __future__ import annotations

import asyncio
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
from lattice.app.ingestion.parsers import ParsingError, parse_uploaded_file
from lattice.app.retrieval.embeddings import EmbeddingProvider
from lattice.app.retrieval.supabase_store import SupabaseVectorStore
from lattice.app.runtime.store import QueuedUpload, RuntimeStore

SUPPORTED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _chunk_text(
    text: str, chunk_size: int = 600, overlap: int = 120
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


def enqueue_ingestion_job(
    *,
    store: RuntimeStore,
    user_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
    user_access_token: str | None,
) -> IngestionJob:
    job_id = f"ing-{uuid4().hex[:12]}"
    queued = IngestionJob(
        job_id=job_id,
        status=INGESTION_STATUS_QUEUED,
        filename=filename,
        content_type=content_type,
        user_id=user_id,
        chunk_count=0,
        error_message=None,
    )
    store.ingestion_jobs[job_id] = queued
    store.queued_uploads[job_id] = QueuedUpload(
        job_id=job_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
        user_access_token=user_access_token,
    )
    return queued


def _build_chunks(
    *,
    job_id: str,
    user_id: str,
    filename: str,
    parsed_text: str,
    embedding_provider: EmbeddingProvider,
) -> list[DocumentChunk]:
    chunk_rows = _chunk_text(parsed_text)
    contents = [content for _, _, content in chunk_rows]
    vectors = embedding_provider.embed_documents(contents) if contents else []

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
        vector = vectors[index - 1] if index - 1 < len(vectors) else []
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                content=content,
                metadata=metadata,
                embedding=tuple(float(value) for value in vector),
            )
        )
    return chunks


def process_ingestion_job(
    *,
    store: RuntimeStore,
    job_id: str,
    embedding_provider: EmbeddingProvider,
    supabase_store: SupabaseVectorStore | None,
) -> IngestionJob:
    upload = store.queued_uploads.get(job_id)
    job = store.ingestion_jobs.get(job_id)
    if not upload or not job:
        raise ValueError("Unknown ingestion job")

    processing = replace(job, status=INGESTION_STATUS_PROCESSING)
    store.ingestion_jobs[job_id] = processing

    if upload.content_type not in SUPPORTED_CONTENT_TYPES:
        failed = replace(
            processing,
            status=INGESTION_STATUS_FAILED,
            error_message="Unsupported file format. Use PDF, DOCX, MD, or TXT.",
        )
        store.ingestion_jobs[job_id] = failed
        return failed

    try:
        parsed_text = parse_uploaded_file(upload.content_type, upload.file_bytes)
        chunks = _build_chunks(
            job_id=job_id,
            user_id=upload.user_id,
            filename=upload.filename,
            parsed_text=parsed_text,
            embedding_provider=embedding_provider,
        )
    except ParsingError as exc:
        failed = replace(
            processing,
            status=INGESTION_STATUS_FAILED,
            error_message=str(exc),
        )
        store.ingestion_jobs[job_id] = failed
        return failed

    if supabase_store and upload.user_access_token:
        try:
            for chunk in chunks:
                supabase_store.upsert_chunk(
                    user_jwt=upload.user_access_token,
                    chunk=chunk,
                )
        except Exception as exc:
            failed = replace(
                processing,
                status=INGESTION_STATUS_FAILED,
                error_message=f"Supabase upsert failed: {exc}",
            )
            store.ingestion_jobs[job_id] = failed
            return failed

    local_chunks = store.private_chunks_by_user.setdefault(upload.user_id, [])
    local_chunks.extend(chunks)
    store.queued_uploads.pop(job_id, None)
    completed = replace(
        processing,
        status=INGESTION_STATUS_SUCCESS,
        chunk_count=len(chunks),
        error_message=None,
    )
    store.ingestion_jobs[job_id] = completed
    return completed


class IngestionWorker:
    def __init__(
        self,
        *,
        store: RuntimeStore,
        embedding_provider: EmbeddingProvider,
        supabase_store: SupabaseVectorStore | None,
    ) -> None:
        self._store = store
        self._embedding_provider = embedding_provider
        self._supabase_store = supabase_store
        self._queue: asyncio.Queue[str] | None = None
        self._task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._shutdown.clear()
            self._queue = asyncio.Queue()
            self._task = asyncio.create_task(self._run(), name="ingestion-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._shutdown.set()
        if self._queue is not None:
            await self._queue.put("__shutdown__")
        await self._task
        self._task = None
        self._queue = None

    async def enqueue(self, job_id: str) -> None:
        if self._queue is None:
            raise RuntimeError("Ingestion worker is not started")
        await self._queue.put(job_id)

    async def _run(self) -> None:
        if self._queue is None:
            return
        while True:
            job_id = await self._queue.get()
            try:
                if job_id == "__shutdown__" and self._shutdown.is_set():
                    return
                try:
                    process_ingestion_job(
                        store=self._store,
                        job_id=job_id,
                        embedding_provider=self._embedding_provider,
                        supabase_store=self._supabase_store,
                    )
                except ValueError:
                    continue
            finally:
                self._queue.task_done()


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

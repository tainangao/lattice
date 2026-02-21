from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

from lattice.app.ingestion.contracts import (
    ChunkMetadata,
    DocumentChunk,
    IngestionJob,
    INGESTION_STAGE_CHUNKING,
    INGESTION_STAGE_COMPLETED,
    INGESTION_STAGE_EMBEDDING,
    INGESTION_STAGE_FAILED,
    INGESTION_STAGE_PARSING,
    INGESTION_STAGE_QUEUED,
    INGESTION_STAGE_UPSERTING,
    INGESTION_STATUS_FAILED,
    INGESTION_STATUS_PROCESSING,
    INGESTION_STATUS_QUEUED,
    INGESTION_STATUS_SUCCESS,
)
from lattice.app.ingestion.parsers import (
    ParsedSegment,
    ParsingError,
    parse_uploaded_file,
)
from lattice.app.retrieval.embeddings import EmbeddingProvider
from lattice.app.retrieval.supabase_store import SupabaseVectorStore
from lattice.app.runtime.store import QueuedUpload, RuntimeStore, persist_runtime_state

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
        stage=INGESTION_STAGE_QUEUED,
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
    persist_runtime_state(store)
    return queued


def _build_chunks(
    *,
    job_id: str,
    user_id: str,
    filename: str,
    parsed_segments: list[ParsedSegment],
    embedding_provider: EmbeddingProvider,
) -> list[DocumentChunk]:
    chunk_rows: list[tuple[int, int, int, str]] = []
    global_offset = 0
    for segment in parsed_segments:
        rows = _chunk_text(segment.text)
        for offset_start, offset_end, content in rows:
            chunk_rows.append(
                (
                    segment.page,
                    global_offset + offset_start,
                    global_offset + offset_end,
                    content,
                )
            )
        global_offset += len(segment.text) + 1

    contents = [content for _, _, _, content in chunk_rows]
    vectors = embedding_provider.embed_documents(contents) if contents else []

    chunks: list[DocumentChunk] = []
    for index, (page, offset_start, offset_end, content) in enumerate(
        chunk_rows, start=1
    ):
        chunk_id = f"{job_id}-chunk-{index}"
        metadata = ChunkMetadata(
            source=filename,
            page=page,
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


def _set_stage(
    *,
    store: RuntimeStore,
    job: IngestionJob,
    stage: str,
    status: str = INGESTION_STATUS_PROCESSING,
    error_message: str | None = None,
) -> IngestionJob:
    next_job = replace(job, status=status, stage=stage, error_message=error_message)
    store.ingestion_jobs[job.job_id] = next_job
    persist_runtime_state(store)
    return next_job


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

    processing = _set_stage(
        store=store,
        job=job,
        stage=INGESTION_STAGE_PARSING,
        status=INGESTION_STATUS_PROCESSING,
    )

    if upload.content_type not in SUPPORTED_CONTENT_TYPES:
        failed = _set_stage(
            store=store,
            job=processing,
            stage=INGESTION_STAGE_FAILED,
            status=INGESTION_STATUS_FAILED,
            error_message="Unsupported file format. Use PDF, DOCX, MD, or TXT.",
        )
        return failed

    try:
        parsed_segments = parse_uploaded_file(upload.content_type, upload.file_bytes)
        processing = _set_stage(
            store=store,
            job=processing,
            stage=INGESTION_STAGE_CHUNKING,
            status=INGESTION_STATUS_PROCESSING,
        )
        processing = _set_stage(
            store=store,
            job=processing,
            stage=INGESTION_STAGE_EMBEDDING,
            status=INGESTION_STATUS_PROCESSING,
        )
        chunks = _build_chunks(
            job_id=job_id,
            user_id=upload.user_id,
            filename=upload.filename,
            parsed_segments=parsed_segments,
            embedding_provider=embedding_provider,
        )
    except ParsingError as exc:
        failed = _set_stage(
            store=store,
            job=processing,
            stage=INGESTION_STAGE_FAILED,
            status=INGESTION_STATUS_FAILED,
            error_message=str(exc),
        )
        return failed

    if supabase_store and upload.user_access_token:
        try:
            processing = _set_stage(
                store=store,
                job=processing,
                stage=INGESTION_STAGE_UPSERTING,
                status=INGESTION_STATUS_PROCESSING,
            )
            for chunk in chunks:
                supabase_store.upsert_chunk(
                    user_jwt=upload.user_access_token,
                    chunk=chunk,
                )
        except Exception as exc:
            failed = _set_stage(
                store=store,
                job=processing,
                stage=INGESTION_STAGE_FAILED,
                status=INGESTION_STATUS_FAILED,
                error_message=f"Supabase upsert failed: {exc}",
            )
            return failed

    local_chunks = store.private_chunks_by_user.setdefault(upload.user_id, [])
    local_chunks.extend(chunks)
    store.queued_uploads.pop(job_id, None)
    completed = replace(
        processing,
        status=INGESTION_STATUS_SUCCESS,
        stage=INGESTION_STAGE_COMPLETED,
        chunk_count=len(chunks),
        error_message=None,
    )
    store.ingestion_jobs[job_id] = completed
    persist_runtime_state(store)
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
            queued_job_ids = [
                job_id
                for job_id, job in self._store.ingestion_jobs.items()
                if job.status in {INGESTION_STATUS_QUEUED, INGESTION_STATUS_PROCESSING}
                and job_id in self._store.queued_uploads
            ]
            for job_id in queued_job_ids:
                await self.enqueue(job_id)

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

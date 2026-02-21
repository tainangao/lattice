from __future__ import annotations

from dataclasses import dataclass


INGESTION_STATUS_QUEUED = "queued"
INGESTION_STATUS_PROCESSING = "processing"
INGESTION_STATUS_SUCCESS = "success"
INGESTION_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ChunkMetadata:
    source: str
    page: int
    offset_start: int
    offset_end: int
    user_id: str


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    metadata: ChunkMetadata
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class IngestionJob:
    job_id: str
    status: str
    filename: str
    content_type: str
    user_id: str
    chunk_count: int
    error_message: str | None

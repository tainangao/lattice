from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

from lattice.app.graph.contracts import GraphEdge
from lattice.app.ingestion.contracts import (
    ChunkMetadata,
    DocumentChunk,
    IngestionJob,
    INGESTION_STAGE_QUEUED,
)
from lattice.app.memory.contracts import ConversationTurn
from lattice.app.observability.contracts import QueryTrace
from lattice.app.retrieval.contracts import RetrievalBundle


@dataclass(frozen=True)
class QueuedUpload:
    job_id: str
    user_id: str
    filename: str
    content_type: str
    file_bytes: bytes
    user_access_token: str | None


@dataclass(frozen=True)
class PendingOAuthState:
    session_id: str
    provider: str
    created_at: int


@dataclass(frozen=True)
class CompletedOAuthSession:
    access_token: str
    refresh_token: str | None
    created_at: int


@dataclass
class RuntimeStore:
    ingestion_jobs: dict[str, IngestionJob] = field(default_factory=dict)
    private_chunks_by_user: dict[str, list[DocumentChunk]] = field(default_factory=dict)
    queued_uploads: dict[str, QueuedUpload] = field(default_factory=dict)
    conversation_turns_by_thread: dict[str, list[ConversationTurn]] = field(
        default_factory=dict
    )
    demo_usage_by_session: dict[str, int] = field(default_factory=dict)
    runtime_keys_by_session: dict[str, str] = field(default_factory=dict)
    oauth_pending_by_state: dict[str, PendingOAuthState] = field(default_factory=dict)
    oauth_completed_by_state: dict[str, CompletedOAuthSession] = field(
        default_factory=dict
    )
    query_embedding_cache: dict[str, tuple[float, ...]] = field(default_factory=dict)
    retrieval_cache: dict[str, RetrievalBundle] = field(default_factory=dict)
    query_trace_log: list[QueryTrace] = field(default_factory=list)
    shared_demo_documents: list[dict[str, str]] = field(default_factory=list)
    shared_graph_edges: list[GraphEdge] = field(default_factory=list)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _runtime_state_path() -> Path:
    base = _repo_root() / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    return base / "runtime_state.json"


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _serialize_chunk(chunk: DocumentChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "content": chunk.content,
        "metadata": {
            "source": chunk.metadata.source,
            "page": chunk.metadata.page,
            "offset_start": chunk.metadata.offset_start,
            "offset_end": chunk.metadata.offset_end,
            "user_id": chunk.metadata.user_id,
        },
        "embedding": list(chunk.embedding),
    }


def _deserialize_chunk(payload: object) -> DocumentChunk | None:
    if not isinstance(payload, dict):
        return None
    chunk_id = payload.get("chunk_id")
    content = payload.get("content")
    metadata = payload.get("metadata")
    embedding = payload.get("embedding")
    if not isinstance(chunk_id, str) or not isinstance(content, str):
        return None
    if not isinstance(metadata, dict) or not isinstance(embedding, list):
        return None
    source = metadata.get("source")
    page = metadata.get("page")
    offset_start = metadata.get("offset_start")
    offset_end = metadata.get("offset_end")
    user_id = metadata.get("user_id")
    if not all(isinstance(value, str) for value in (source, user_id)):
        return None
    if not all(isinstance(value, int) for value in (page, offset_start, offset_end)):
        return None
    if not all(isinstance(value, (int, float)) for value in embedding):
        return None
    return DocumentChunk(
        chunk_id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            source=source,
            page=page,
            offset_start=offset_start,
            offset_end=offset_end,
            user_id=user_id,
        ),
        embedding=tuple(float(value) for value in embedding),
    )


def _serialize_job(job: IngestionJob) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "stage": job.stage,
        "filename": job.filename,
        "content_type": job.content_type,
        "user_id": job.user_id,
        "chunk_count": job.chunk_count,
        "error_message": job.error_message,
    }


def _deserialize_job(payload: object) -> IngestionJob | None:
    if not isinstance(payload, dict):
        return None
    job_id = payload.get("job_id")
    status = payload.get("status")
    stage = payload.get("stage")
    filename = payload.get("filename")
    content_type = payload.get("content_type")
    user_id = payload.get("user_id")
    chunk_count = payload.get("chunk_count")
    error_message = payload.get("error_message")
    if not all(
        isinstance(value, str)
        for value in (job_id, status, stage, filename, content_type, user_id)
    ):
        return None
    if not isinstance(chunk_count, int):
        return None
    if error_message is not None and not isinstance(error_message, str):
        return None
    return IngestionJob(
        job_id=job_id,
        status=status,
        stage=stage,
        filename=filename,
        content_type=content_type,
        user_id=user_id,
        chunk_count=chunk_count,
        error_message=error_message,
    )


def _serialize_upload(upload: QueuedUpload) -> dict[str, object]:
    return {
        "job_id": upload.job_id,
        "user_id": upload.user_id,
        "filename": upload.filename,
        "content_type": upload.content_type,
        "file_bytes_b64": base64.b64encode(upload.file_bytes).decode("ascii"),
        "user_access_token": upload.user_access_token,
    }


def _deserialize_upload(payload: object) -> QueuedUpload | None:
    if not isinstance(payload, dict):
        return None
    job_id = payload.get("job_id")
    user_id = payload.get("user_id")
    filename = payload.get("filename")
    content_type = payload.get("content_type")
    file_bytes_b64 = payload.get("file_bytes_b64")
    user_access_token = payload.get("user_access_token")
    if not all(
        isinstance(value, str)
        for value in (job_id, user_id, filename, content_type, file_bytes_b64)
    ):
        return None
    if user_access_token is not None and not isinstance(user_access_token, str):
        return None
    try:
        file_bytes = base64.b64decode(file_bytes_b64.encode("ascii"), validate=True)
    except Exception:
        return None
    return QueuedUpload(
        job_id=job_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
        user_access_token=user_access_token,
    )


def _load_persisted_runtime_state() -> dict[str, object]:
    path = _runtime_state_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return {}
        return payload
    except Exception:
        return {}


def persist_runtime_state(store: RuntimeStore) -> None:
    payload = {
        "ingestion_jobs": [
            _serialize_job(job) for job in store.ingestion_jobs.values()
        ],
        "private_chunks_by_user": {
            user_id: [_serialize_chunk(chunk) for chunk in chunks]
            for user_id, chunks in store.private_chunks_by_user.items()
        },
        "queued_uploads": [
            _serialize_upload(upload) for upload in store.queued_uploads.values()
        ],
    }
    path = _runtime_state_path()
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    temp_path.replace(path)


def clear_runtime_state_persistence() -> None:
    path = _runtime_state_path()
    if path.exists():
        path.unlink()


def _hydrate_ingestion_jobs(raw_jobs: object) -> dict[str, IngestionJob]:
    if not isinstance(raw_jobs, list):
        return {}
    jobs: dict[str, IngestionJob] = {}
    for row in raw_jobs:
        job = _deserialize_job(row)
        if not job:
            continue
        jobs[job.job_id] = job
    return jobs


def _hydrate_private_chunks(raw_chunks: object) -> dict[str, list[DocumentChunk]]:
    if not isinstance(raw_chunks, dict):
        return {}
    chunks_by_user: dict[str, list[DocumentChunk]] = {}
    for user_id, rows in raw_chunks.items():
        if not isinstance(user_id, str) or not isinstance(rows, list):
            continue
        hydrated = [chunk for row in rows if (chunk := _deserialize_chunk(row))]
        if hydrated:
            chunks_by_user[user_id] = hydrated
    return chunks_by_user


def _hydrate_queued_uploads(raw_uploads: object) -> dict[str, QueuedUpload]:
    if not isinstance(raw_uploads, list):
        return {}
    uploads: dict[str, QueuedUpload] = {}
    for row in raw_uploads:
        upload = _deserialize_upload(row)
        if not upload:
            continue
        uploads[upload.job_id] = upload
    return uploads


def _build_store() -> RuntimeStore:
    repo_root = _repo_root()
    demo_docs_path = repo_root / "data" / "prototype" / "private_documents.json"
    graph_path = repo_root / "data" / "prototype" / "graph_edges.json"

    demo_docs_raw = _load_json(demo_docs_path)
    graph_raw = _load_json(graph_path)

    demo_docs: list[dict[str, str]] = []
    if isinstance(demo_docs_raw, list):
        for item in demo_docs_raw:
            if isinstance(item, dict):
                source = item.get("source")
                chunk_id = item.get("chunk_id")
                content = item.get("content")
                if (
                    isinstance(source, str)
                    and isinstance(chunk_id, str)
                    and isinstance(content, str)
                ):
                    demo_docs.append(
                        {
                            "source": source,
                            "chunk_id": chunk_id,
                            "content": content,
                        }
                    )

    graph_edges: list[GraphEdge] = []
    if isinstance(graph_raw, dict) and isinstance(graph_raw.get("edges"), list):
        for edge in graph_raw["edges"]:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source")
            relationship = edge.get("relationship")
            target = edge.get("target")
            evidence = edge.get("evidence")
            if all(
                isinstance(value, str)
                for value in (source, relationship, target, evidence)
            ):
                graph_edges.append(
                    GraphEdge(
                        source=source,
                        relationship=relationship,
                        target=target,
                        evidence=evidence,
                    )
                )

    persisted = _load_persisted_runtime_state()
    ingestion_jobs = _hydrate_ingestion_jobs(persisted.get("ingestion_jobs"))
    private_chunks_by_user = _hydrate_private_chunks(
        persisted.get("private_chunks_by_user")
    )
    queued_uploads = _hydrate_queued_uploads(persisted.get("queued_uploads"))

    for upload_job_id in queued_uploads:
        if upload_job_id not in ingestion_jobs:
            upload = queued_uploads[upload_job_id]
            ingestion_jobs[upload_job_id] = IngestionJob(
                job_id=upload.job_id,
                status="queued",
                stage=INGESTION_STAGE_QUEUED,
                filename=upload.filename,
                content_type=upload.content_type,
                user_id=upload.user_id,
                chunk_count=0,
                error_message=None,
            )

    return RuntimeStore(
        ingestion_jobs=ingestion_jobs,
        private_chunks_by_user=private_chunks_by_user,
        queued_uploads=queued_uploads,
        shared_demo_documents=demo_docs,
        shared_graph_edges=graph_edges,
    )


runtime_store = _build_store()

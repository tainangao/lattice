from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RetrievalMode(str, Enum):
    DIRECT = "direct"
    DOCUMENT = "document"
    GRAPH = "graph"
    BOTH = "both"


class RouteDecision(BaseModel):
    mode: RetrievalMode
    reason: str


class SourceSnippet(BaseModel):
    source_type: str
    source_id: str
    text: str
    score: float = Field(ge=0.0)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)


class QueryResponse(BaseModel):
    question: str
    route: RouteDecision
    answer: str
    snippets: list[SourceSnippet]


class PrivateUploadRequest(BaseModel):
    filename: str = Field(min_length=1)
    content: str = Field(min_length=1)

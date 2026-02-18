---
source: Context7 API + official docs
library: Chainlit, LangGraph, FastAPI, Supabase, Neo4j, Google GenAI
package: agentic-rag-python
topic: phase-1-prototype-minimal-setup-async-retrieval
fetched: 2026-02-18T02:50:33+00:00
official_docs: https://docs.chainlit.io/, https://docs.langchain.com/oss/python/langgraph, https://fastapi.tiangolo.com/, https://supabase.com/docs/guides/ai/vector-columns, https://neo4j.com/docs/neo4j-graphrag-python/current/, https://googleapis.github.io/python-genai/
---

# Phase 1: Agentic RAG in Python (concise, implementation-first)

## 1) Minimal install commands

```bash
# Core app
pip install fastapi "uvicorn[standard]" chainlit

# Agent graph + model SDK
pip install langgraph langchain google-genai

# Vector/DB layers
pip install supabase neo4j neo4j-graphrag
```

Notes:
- `supabase` package needs Python >= 3.9.
- `neo4j-graphrag` supports Python 3.10+ and Neo4j >= 5.18.1 (Aura >= 5.18.0).
- Use `neo4j` package name (not `neo4j-driver`, deprecated).

## 2) Required env vars (minimum)

```bash
# Chainlit / app
CHAINLIT_AUTH_SECRET=replace-me-if-using-auth

# Gemini SDK (Developer API)
GEMINI_API_KEY=your_key
# or GOOGLE_API_KEY=your_key (takes precedence over GEMINI_API_KEY)

# Supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<anon-or-service-role-key>

# Neo4j
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

Optional (Gemini via Vertex AI):

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

## 3) FastAPI + Chainlit minimal integration

```python
# my_cl_app.py
import chainlit as cl

@cl.on_chat_start
async def start():
    await cl.Message(content="Chainlit is up").send()
```

```python
# main.py
from fastapi import FastAPI
from chainlit.utils import mount_chainlit

app = FastAPI()
mount_chainlit(app=app, target="my_cl_app.py", path="/chainlit")

@app.get("/health")
async def health():
    return {"ok": True}
```

Run:

```bash
uvicorn main:app --reload
```

## 4) LangGraph async retrieval flow (basic shape)

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    question: str
    docs: list[str]
    answer: str

async def retrieve(state: State):
    # replace with real retriever call
    return {"docs": [f"context for: {state['question']}"]}

async def generate(state: State):
    # replace with Gemini call
    return {"answer": f"A: {state['question']}\nUsing: {state['docs'][0]}"}

graph = (
    StateGraph(State)
    .add_node("retrieve", retrieve)
    .add_node("generate", generate)
    .add_edge(START, "retrieve")
    .add_edge("retrieve", "generate")
    .add_edge("generate", END)
    .compile()
)

# async invoke
# result = await graph.ainvoke({"question": "What is pgvector?", "docs": [], "answer": ""})
```

Async gotcha:
- For Python < 3.11, pass config through explicitly in async model calls to avoid context propagation issues in streaming/ainvoke patterns.

## 5) Supabase + Postgres/pgvector (practical baseline)

Create extension/table/function (SQL):

```sql
create extension if not exists vector with schema extensions;

create table if not exists documents (
  id bigserial primary key,
  content text not null,
  embedding extensions.vector(384)
);

create or replace function match_documents(
  query_embedding extensions.vector(384),
  match_threshold float,
  match_count int
)
returns table (id bigint, content text, similarity float)
language sql stable
as $$
  select
    d.id,
    d.content,
    1 - (d.embedding <=> query_embedding) as similarity
  from documents d
  where 1 - (d.embedding <=> query_embedding) > match_threshold
  order by d.embedding <=> query_embedding asc
  limit match_count;
$$;
```

Call from Python (async client + RPC):

```python
import os
from supabase import create_async_client

async def match(embedding: list[float]):
    supabase = await create_async_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    res = await supabase.rpc("match_documents", {
        "query_embedding": embedding,
        "match_threshold": 0.78,
        "match_count": 5,
    }).execute()
    return res.data
```

pgvector gotchas:
- Use the same embedding model for both stored docs and query vectors.
- Through PostgREST clients, put vector operators inside SQL functions and call with `rpc()`.
- For indexed search, order by distance expression directly (`embedding <=> query_embedding`), not by computed alias.

## 6) Neo4j + neo4j-graphrag quickstart

```python
import os
from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.generation import GraphRAG

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
)

retriever = VectorRetriever(
    driver=driver,
    index_name="document-embeddings",
    embedder=OpenAIEmbeddings(model="text-embedding-3-large"),
)
rag = GraphRAG(retriever=retriever, llm=OpenAILLM(model_name="gpt-4o"))

resp = rag.search(query_text="How does retrieval work?", retriever_config={"top_k": 3})
print(resp.answer)
driver.close()
```

Async note:
- `neo4j` Python driver has full async APIs (`AsyncGraphDatabase`).
- `neo4j-graphrag` examples are primarily sync-style; use async at DB layer where needed.

## 7) Gemini Python SDK async usage

```python
import asyncio
from google import genai

client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY

async def main():
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents="Summarize: retrieval augmented generation in one paragraph",
    )
    print(response.text)

    await client.aio.aclose()

asyncio.run(main())
```

Compatibility gotchas:
- Use `google-genai` (current SDK). `google-generativeai` is legacy/deprecated.
- If both `GOOGLE_API_KEY` and `GEMINI_API_KEY` are set, `GOOGLE_API_KEY` wins.
- Prefer `async with Client().aio as aclient:` or explicit `aclose()` to avoid leaking async resources.

## 8) Quick runnable Phase 1 flow (one request path)

1. FastAPI endpoint receives question.
2. LangGraph `retrieve` node calls Supabase RPC `match_documents` (or Neo4j retriever).
3. `generate` node calls Gemini async `generate_content` with retrieved context.
4. Return answer + top snippets; optionally expose same flow in Chainlit UI.

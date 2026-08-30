# OmniRAG Studio

Production-ready multi-source RAG (Retrieval-Augmented Generation) chatbot. Ingest PDFs, CSVs, and web pages; embed them locally with HuggingFace; persist vectors in ChromaDB; and answer questions with source citations.

The backend is FastAPI. The optional UI is Streamlit. Domain logic (ingestion, vector store, RAG, analytics) never imports FastAPI or Streamlit.

## Architecture flow

```
PDF / CSV / URL
        │
        ▼
 ingestion loaders  →  recursive text splitter
        │
        ▼
 HuggingFace embeddings (all-MiniLM-L6-v2, CPU)
        │
        ▼
 ChromaDB collection (CHROMA_DB_PATH)
        │
        ▼
 POST /api/v1/chat/query
        │
        ├─ similarity search (top-k)
        ├─ optional OpenAI LLM (gpt-4o-mini)
        └─ extractive fallback if the LLM key/quota is missing
        │
        ▼
 { answer, citations[{source, page/row}], session_id }
```

| Layer | Path | Responsibility |
|-------|------|----------------|
| HTTP | `backend/api/v1/` | Routers: ingest, chat, analytics. Registered in `backend/api/router.py`. |
| Config | `backend/config.py` | Pydantic Settings from `.env`. No hardcoded secrets. |
| Ingestion | `backend/ingestion/` | PDF, CSV, and web loaders plus chunking. |
| Vector store | `backend/vectorstore/` | Local HuggingFace embeddings, ChromaDB, retriever. |
| RAG | `backend/rag/` | Prompt, chain, citations, in-process session memory. |
| Analytics | `backend/analytics/` | SQLite logging (placeholder until a later phase). |
| Frontend | `frontend/` | Streamlit UI; talks to the API only via `frontend/utils/api_client.py`. |
| Tests | `tests/` | pytest, mirroring backend packages. |

## Setup

Python 3.11+ recommended. From the project root:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
copy .env.example .env
```

On macOS/Linux use `cp .env.example .env` instead of `copy`.

### Local HuggingFace embeddings

The default embedding provider is **local** and does **not** require an OpenAI key:

```
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

On first embed, `sentence-transformers` downloads `all-MiniLM-L6-v2` (about 90 MB) into the HuggingFace cache and runs it on CPU. HuggingFace classes are imported lazily so `GET /docs` and app startup do not load PyTorch.

Optional chat generation uses OpenAI (`LLM_MODEL=gpt-4o-mini`). If `OPENAI_API_KEY` is missing or the quota is exceeded, chat still returns HTTP 200 with an extractive, cited answer from retrieved chunks.

Never commit `.env`. Keep real keys out of git.

### Run FastAPI

```bash
python -m backend.main
```

or:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/health` → `{"status":"ok","app":"OmniRAG Studio"}`.

Interactive docs (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Optional Streamlit UI

```bash
streamlit run frontend/app.py
```

## API endpoints

Base path: `/api/v1`. Successful JSON bodies are typed Pydantic models. Errors use `{"detail": "..."}` with the HTTP status below.

### `POST /api/v1/ingest/file`

Upload a **PDF** or **CSV**. The handler dispatches on file extension.

- Content type: `multipart/form-data`
- Fields:
  - `file` (required): `.pdf` or `.csv`
  - `collection_name` (optional form field, default `default_collection`)
- Success **200**: `{source, document_count, chunk_count, snippets, collection_name, stored_count}`
- **400**: empty file, unsupported extension, unreadable/empty source
- **413**: file larger than 25 MB
- **422**: missing `file` part

Equivalent typed routes still exist: `POST /api/v1/ingest/pdf` and `POST /api/v1/ingest/csv`.

### `POST /api/v1/ingest/url`

Fetch a public HTTP(S) page, strip chrome (nav/header/footer/script), chunk, embed, and store.

- Content type: `application/json`
- Body: `{ "url": "https://example.com/docs", "collection_name": "default_collection" }`
- Success **200**: same ingest payload as `/file`
- **400**: no extractable text, fetch/parse failure
- **422**: invalid URL or blank `collection_name`

### `POST /api/v1/chat/query`

Retrieve from a collection and return a grounded answer with citations.

- Content type: `application/json`
- Body: `{ "query": "…", "collection_name": "default_collection", "session_id": "optional" }`
- Success **200**: `{ "answer": "…", "citations": [{ "source": "…", "page/row": "…" }], "session_id": "…" }`
- **404**: collection does not exist (ingest first)
- **422**: empty/whitespace query, invalid types
- **502** / **503** / **429**: RAG or vector-store failures that are not handled by the extractive fallback

`page/row` is a PDF page number, CSV row index, or the source URL for web pages.

### `POST /api/v1/chat/clear`

Drop in-process conversational memory for a session.

- Content type: `application/json`
- Body: `{ "session_id": "sess-1" }`
- Success **200**: `{ "session_id": "sess-1", "cleared": true }` (`cleared` is `false` if the session was already empty)
- **422**: missing or blank `session_id`

### Other routes

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/health` | Liveness. |
| `POST` | `/api/v1/ingest/store` | Persist pre-chunked `{page_content, metadata}` documents. |
| `POST` | `/api/v1/chat/stream` | **501** — streaming not implemented. |
| `GET` | `/api/v1/analytics/metrics` | **501** — analytics not implemented. |

## Testing with Swagger UI

1. Start the API (`python -m backend.main`).
2. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
3. **Ingest** — expand `POST /api/v1/ingest/file`, click **Try it out**, choose a `.pdf` or `.csv`, optionally set `collection_name`, then **Execute**. Confirm `200` and a non-zero `stored_count`.
4. **URL ingest** — `POST /api/v1/ingest/url` with a public `https://` URL and the same `collection_name`.
5. **Chat** — `POST /api/v1/chat/query` with that `collection_name` and a question that the document can answer. Confirm `answer` plus `citations`.
6. **Clear** — `POST /api/v1/chat/clear` with the `session_id` returned from chat.
7. **Edge cases** — empty file → `400`; unknown `collection_name` on chat → `404`; `"query": ""` → `422`.

## Automated tests

From the project root, with the virtualenv active:

```bash
python -m pytest
```

Tests mock embeddings, Chroma writes, and LLM calls. They do not hit live OpenAI. HuggingFace/torch are not imported when serving `/docs`.

## Configuration

See `.env.example`. Important variables:

| Variable | Default | Role |
|----------|---------|------|
| `EMBEDDING_PROVIDER` | `huggingface` | `huggingface` (local) or `openai` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model id |
| `CHROMA_DB_PATH` | `./chroma_db` | Persistent vector index |
| `DEFAULT_COLLECTION_NAME` | `default_collection` | Used when clients omit a name |
| `OPENAI_API_KEY` | empty | Optional; chat LLM only (or OpenAI embeddings) |
| `LLM_MODEL` | `gpt-4o-mini` | Chat model when a key is present |
| `RAG_TOP_K` | `4` | Retrieval depth |
| `DATABASE_URL` | `sqlite:///./analytics.db` | Analytics SQLite (future) |

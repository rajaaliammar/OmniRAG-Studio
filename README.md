# OmniRAG Studio

Multi-source RAG chatbot with real-time analytics. Ingest PDFs, CSVs, and web pages; store embeddings in ChromaDB; answer questions with source citations via LangChain; log queries and cost to SQLite.

## Status

Project skeleton. Domain modules are placeholders ready for implementation.

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then set OPENAI_API_KEY
```

### Backend (FastAPI)

```bash
python -m backend.main
# or: uvicorn backend.main:app --reload --port 8000
```

Health check: `GET http://127.0.0.1:8000/health`

### Frontend (Streamlit)

```bash
streamlit run frontend/app.py
```

## Layout

| Path | Role |
|------|------|
| `backend/api/` | HTTP routers (ingestion, chat, analytics) |
| `backend/ingestion/` | PDF, CSV, and web loaders + text splitting |
| `backend/vectorstore/` | Embeddings, ChromaDB, retriever |
| `backend/rag/` | Prompts, chains, citations |
| `backend/analytics/` | SQLite models and query/cost logging |
| `frontend/` | Streamlit UI |
| `tests/` | Unit tests |

## Configuration

See `.env.example` for `OPENAI_API_KEY`, `CHROMA_DB_PATH`, and `DATABASE_URL`.

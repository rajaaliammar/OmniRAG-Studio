# OmniRAG Studio — Next.js Frontend

Modern App Router dashboard for document ingestion and grounded RAG chat.

## Stack

- Next.js 16 (App Router)
- TypeScript
- Tailwind CSS v4
- shadcn/ui base components
- axios + lucide-react

## Setup

```bash
cd frontend
npm install
copy .env.example .env.local
```

On macOS/Linux: `cp .env.example .env.local`

Ensure the FastAPI backend is running on `http://127.0.0.1:8000`.

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The header polls `GET /health` every 30 seconds.

## Folder structure

| Path | Purpose |
|------|---------|
| `app/` | App Router pages and global styles |
| `components/layout/` | Dashboard shell, sidebar, header |
| `components/ingestion/` | Ingestion module (Phase 1 shell) |
| `components/chat/` | Chat module (Phase 1 shell) |
| `components/ui/` | shadcn/ui primitives |
| `hooks/` | Client hooks (`useHealth`, `useCollections`) |
| `lib/` | API client, config, utilities |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | FastAPI origin |

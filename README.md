# SmartCampus AI

A standalone, demo-ready university-orientation and admissions workflow based on `Projet_IAG_p3_26_27.pdf`. The workspace did not contain an application, so this creates a new Next.js and FastAPI app without changing the separate `browser-reader-mcp` folder.

## What is included

- Candidate accounts and no-account guest conversations, with guest-session memory, expiry, a per-session message limit, and guest-history linking at sign-in or registration.
- Candidate profiles, French / Tunisian Arabic / Arabizi language routing, text chat, optional voice-note transcription, and a conversation history.
- Source-retrieval answers with passage-level citations, PostgreSQL/pgvector persistence, a local hashed multilingual-vector fallback, and an optional OpenAI-compatible chat provider.
- Programme catalogue and management for IIT and ISB, including tuition, prerequisites, source URLs, sample-data labels, and keyword-overlap comparisons.
- Consent-gated pre-registration, scoped academic review, interview-team questionnaire summaries, proposed appointment times, and candidate confirmation.
- Role-aware workspaces for IIT/ISB academic teams, interview coordinators, directors, and administrators.
- In-app notification records, optional SMTP delivery, live database statistics, document indexing, and an admin-triggered language/retrieval evaluation suite.
- PostgreSQL schema migration and a SQLite local-development path.

Official study data, admission decisions, and appointment availability are not invented. The seeded catalogue and knowledge sources are transcribed from the public pages of IIT (Institut International de Technologie) and ISB (International School of Business), Sfax, with a `source_url` on every programme and document. Fields the institutions do not publish (IIT application deadlines, total duration of one licence, ISB tuition) are recorded as "to confirm" and must be routed to admissions rather than guessed. The single fee-estimate document is marked `is_sample=true` and is explicitly non-official. Re-check published fees before any demo, and keep demo questionnaire completion separate from any knowledge or admission score.

## Run locally on Windows

Use Python 3.8+ and Node.js 20+. Run these commands from the workspace root.

1. Install frontend packages and start Next.js:

   ```powershell
   npm install
   Copy-Item .env.local.example .env.local
   npm run dev
   ```

2. In a second terminal, set up and start FastAPI:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r backend\requirements.txt
   Copy-Item backend\.env.example backend\.env
   Set-Location backend
   uvicorn app.main:app --reload --env-file .env
   ```

3. Open `http://localhost:3000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

The default development database is `backend\smartcampus.db`. The app creates its local schema and seeds IIT/ISB programme and knowledge-source records transcribed from the institutions' public pages (plus one clearly labelled non-official fee estimate). A new candidate can register in the app. Development-only staff accounts are seeded when `SEED_DEMO_DATA=true`:

| Role | Email |
|---|---|
| Platform administrator | `demo.admin@smartcampus.example.com` |
| IIT academic adviser | `demo.iit@smartcampus.example.com` |
| ISB academic adviser | `demo.isb@smartcampus.example.com` |
| Interview coordinator | `demo.interviewer@smartcampus.example.com` |
| Admissions director | `demo.director@smartcampus.example.com` |

The local demo password is `CampusDemo2026!` for these seeded users. Change `DEMO_PASSWORD` for a local team. Demo accounts are disabled in production, and no demo password should be reused outside local development.

## PostgreSQL and migrations

Create a PostgreSQL database with the pgvector extension available. Copy `backend\.env.example` to `backend\.env` and set `DATABASE_URL`, for example:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/smartcampus
APP_ENV=production
SEED_DEMO_DATA=false
JWT_SECRET=<a-random-secret-at-least-32-characters>
```

From `backend\`, run the versioned schema baseline before starting the API:

```powershell
alembic upgrade head
uvicorn app.main:app --env-file .env
```

Production startup does not create or alter tables automatically. Create future migrations after model changes and review them before applying them. The initial migration creates the schema represented by the application models and enables pgvector.

SQLite is intended for local demos. PostgreSQL uses cosine-distance search through pgvector. Without an embedding key, the app stores deterministic hashed multilingual term and bigram vectors; these are a lightweight retrieval fallback, not a trained semantic embedding model. When an OpenAI-compatible API key is configured, indexed documents and queries use the configured embedding service instead. Configure embedding settings before indexing official documents so stored and query vectors use the same model and dimensions.

## Retrieval

Knowledge documents are split into overlapping passages stored in `document_chunks` (`RAG_CHUNK_SIZE`, default 800 characters; `RAG_CHUNK_OVERLAP`, default 120). Search blends BM25 lexical scores with vector similarity (`RAG_VECTOR_WEIGHT`, default 0.3 without an embedding provider and 0.5 with one), keeps one passage per document, and returns passage-level snippets in each citation. The API serves the best passage to the chat model instead of the whole document.

Re-index after changing `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS` by calling `POST /api/admin/documents/reindex` as an administrator. `DELETE /api/admin/documents/{id}` removes a source and its passages. With SQLite the vectors are stored as JSON; PostgreSQL uses a pgvector column.

## Optional integrations

Set these in `backend\.env` only when you have chosen and configured the provider:

| Variables | Purpose |
|---|---|
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CHAT_MODEL` | OpenAI-compatible assistant responses |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | Document/query embeddings; dimensions must match |
| `TRANSCRIPTION_MODEL` | Audio transcription endpoint, default `whisper-1` |
| `EVALUATION_MODELS` | Comma-separated chat models for the six fixed evaluation prompts |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | Email notifications |
| `FRONTEND_ORIGINS` | Comma-separated allowed browser origins |

When SMTP is not configured, notification events are stored in the candidate workspace and marked `not_configured`; they are not reported as sent. Appointment times are manually proposed and confirmed by the candidate; no external calendar is connected. The evaluation endpoint `/api/admin/evaluations` is an admin-triggered smoke test, not proof of answer quality or dialect competence. Provider comparisons send six fixed prompts per configured model and may incur charges. Without an embedding provider, retrieval uses lexical overlap over the available text instead of treating hashed demo vectors as semantic embeddings.

## Roles and human review

- Candidates control their own profile and see their own conversations, pre-registration, questionnaires, appointments, and notifications.
- IIT and ISB academic accounts are scoped to their institution's applications and can review their own programme requests.
- Interview coordinators propose meeting times; candidates confirm them.
- Administrators manage users, catalogue records, and indexed documents.
- Assistant recommendations are transparent keyword overlaps, not an eligibility score. An academic adviser must verify orientation recommendations. An administrator may mark catalogue entries as sample, but official decisions remain human-owned.

## Validation

From the workspace root:

```powershell
npm run typecheck
npm run build
```

From the `backend\` directory after activating the virtual environment:

```powershell
python -m unittest discover -s tests -v
```

Never expose the development server or PostgreSQL to an untrusted network. Before deployment, configure production secrets, HTTPS, trusted origins, backups, SMTP/calendar providers, verified institutional content, retention policy, and a reviewed security/privacy process.

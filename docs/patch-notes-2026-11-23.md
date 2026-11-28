# SmartCampus AI — Patch Notes / Handover

**Date:** 2026‑11‑23
**Repo:** https://github.com/Raissi02/CompusAI (private, `main`)
**HEAD:** `43bb521` — *fix: detect message language, isolate retrieval query, boost institution and title matches*
**Previous:** `4ac3569` — *feat: add chunk-level hybrid retrieval and passage citations*
**Base:** `4c2e3ea` (upstream `rabiebaccouch/CompusAI`)

---

## 1. What is done

### 1.1 Institutional data (replaces the 3 placeholder documents)

- **15 programmes** seeded from the official IIT/ISB pages, each with `source_url`:
  - IIT: Cycle préparatoire, Licence GL&SI, Licence MSI, Architecture (ISA), Génie Civil, Génie Industriel, Génie Informatique, Génie Mécanique, Génie des Procédés, Mastère Industries 4.0.
  - ISB: LBA, Business Intelligence, LNG, MBA, MSc Finance.
- **16 knowledge documents** (fees, admission procedure, scholarships, accreditations, ISB licences/masters, calendar, equivalence, FAQ, plus one clearly non‑official fee estimate marked `is_sample=true`).
- Publication facts captured: per‑9‑month indicative fees, +800 DT/€ registration, +5%/year, no refunds, 5% full‑payment discount, 01/10 exchange‑rate rule, bank details, 4 scholarship types (≤10% of new enrolments, apply within 1 week).
- Gaps are written as *"to confirm"* rather than invented: IIT deadlines/calendar, total duration of Licence MSI, Génie Télécommunications availability, 2026‑27 fee schedule, equivalence procedure, guide étudiant.

**Deliberate policy:** the assistant never states admission decisions, never guarantees equivalence, and routes those to a human adviser.

### 1.2 Retrieval (RAG Phase 1)

- `DocumentChunk` table + Alembic `0002_document_chunks` (pgvector on Postgres, JSON on SQLite).
- Sentence‑aware chunker: 800 chars / 120 overlap (`RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`).
- Hybrid search: BM25 + vector cosine, weighted blend (not RRF), one passage per document, institution filter.
  - `RAG_VECTOR_WEIGHT` = 0.3 without an embedding provider, 0.5 with one.
  - Institution hint boost (IIT/ISB) ×1.15 / ×0.85, title‑match boost up to +24%.
  - Accent folding + plural stemming, FR/EN interrogatives as stop‑words.
- Passage‑level citations: `title`, `institution`, `is_sample`, `source_url`, **`snippet`**, **`chunk_id`**.
- Admin endpoints: `POST /api/admin/documents/reindex`, `DELETE /api/admin/documents/{id}`; creation chunks immediately.
- Language detection per message (`fr`, `en`, Arabic script, Arabizi) instead of inheriting the previous turn.
- Retrieval query = the user question only; profile memory is used only for very short questions (<3 words) and always for the LLM prompt.

### 1.3 Verification

- Tests: **7/7** (workflow + reindex/chunk‑citation test).
- Live evaluation: `language_detection 1.0`, `institution_retrieval_recall 1.0`, `expected_source_recall 1.0`.
- Live DB: 16 documents → 28 chunks, 0 unchunked; reindex idempotent.
- E2E script (candidate register → profile → chat → admin add/reindex/delete) passes.

---

## 2. Current limitations

1. **No LLM running.** ZScaler on this laptop blocks `registry.ollama.ai`, `huggingface.co`, `ollama.com` ("Generative AI and ML Applications"). Ollama v0.40.17 is installed and `ollama serve` works, but no model can be pulled. Chat returns the canned fallback: *"I found relevant information in the indexed sources, but … no language‑model provider."*
2. **Off‑topic questions can still return one citation.** With hashed vectors, cosine similarity can exceed `MIN_VECTOR_SIMILARITY = 0.35` on shared function words (`est`, `la`, `de`). Fix pending (see §5.1).
3. ISB tuition is not published on the official site → stored as "contact ISB".
4. Voice transcription needs `/audio/transcriptions`; Ollama does **not** provide it. Local Whisper is a separate task.
5. GitHub token is embedded in `.git/config` for both remotes — rotate it and switch to a credential helper.

---

## 3. Run the app (current laptop)

```powershell
# backend
cd D:\Toutou
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env
# run from D:\Toutou\backend with the venv path above, or activate the venv first

# frontend (second terminal, D:\Toutou)
npm run dev
```

- Web: http://localhost:3000 — API docs: http://127.0.0.1:8000/docs
- Demo accounts (`CampusDemo2026!`): `demo.admin@`, `demo.iit@`, `demo.isb@`, `demo.interviewer@`, `demo.director@` `smartcampus.example.com`
- Tests: `cd backend; ..\.venv\Scripts\python.exe -m unittest discover -s tests -v`

---

## 4. Ollama on a PC without ZScaler

Two valid paths. Pick A if that PC can run the whole app; pick B if you only want to bring models back to this laptop.

### Path A — run the app on the unrestricted PC

1. Install Ollama (same or newer version than 0.40.17): `winget install --id Ollama.Ollama` or the installer from https://ollama.com/download.
2. Set the model directory (avoid filling C:):
   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_MODELS","D:\ollama\models","User")
   ```
   (Linux/macOS: `export OLLAMA_MODELS=/data/ollama/models`)
3. Start the server and pull the two models:
   ```powershell
   ollama serve
   ollama pull qwen3:4b      # ~2.6 GB, CPU chat model (FR/EN)
   ollama pull bge-m3        # ~1.2 GB, multilingual embeddings, 1024 dims
   ollama list
   ```
4. Verify the embedding dimension — it must be 1024:
   ```powershell
   curl.exe -s http://127.0.0.1:11434/v1/embeddings -H "Content-Type: application/json" `
     -d '{"model":"bge-m3","input":"test"}' |
     ConvertFrom-Json | % { $_.data[0].embedding.Count }
   ```
5. Point the backend at it (`backend/.env`):
   ```text
   OPENAI_BASE_URL=http://127.0.0.1:11434/v1
   OPENAI_API_KEY=ollama
   CHAT_MODEL=qwen3:4b
   EMBEDDING_MODEL=bge-m3
   EMBEDDING_DIMENSIONS=1024
   ```
6. Copy the repo, create the venv, install `backend/requirements.txt`, run `npm install`.
7. **Rebuild the database** because the embedding dimension changes (1536 → 1024):
   ```powershell
   # stop the API first
   Copy-Item backend\smartcampus.db backend\smartcampus.db.bak-<date> -Force
   Remove-Item backend\smartcampus.db
   # start the API: dev mode recreates the schema and re-embeds the seed corpus
   ```
8. Verify:
   - `POST /api/admin/evaluations` as admin → all three checks `passed=true`.
   - Ask “Quels sont les frais du cycle préparatoire à l’IIT ?” → a composed, cited answer, not the fallback.
   - `GET /api/admin/documents` → every document has `chunks > 0`.

### Path B — pull models there, copy them here (recommended if this laptop stays the demo machine)

1. Follow steps 1–4 above on the unrestricted PC.
2. Stop Ollama (`ollama` tray → Quit, or `Stop-Process -Name ollama`).
3. Copy the **whole models directory** to external storage:
   - `D:\ollama\models` → contains `blobs\` and `manifests\`.
4. On this laptop: stop the API and Ollama, set `OLLAMA_MODELS=D:\ollama\models`, copy the directory back to the same path, start `ollama serve`, then `ollama list` must show `qwen3:4b` and `bge-m3`.
5. Copy caveat: use the **same Ollama version** on both machines (0.40.17 here) and the same OS family. If `ollama list` shows nothing, the manifests were not copied.
6. Apply `backend/.env` from step 5 above, then do the DB rebuild from step 7 and verify from step 8.

### Benchmark before committing to the model

Run on the machine that will serve the demo, with the app closed:

```powershell
$prompt = @"
Tu es un assistant d'orientation. Réponds en français, cite [1].
[1] IIT — Cycle préparatoire
Le cycle préparatoire est accessible avec un baccalauréat scientifique. Frais indicatifs : 556 DT par 9 mois.
Question : Quels sont les prérequis et les frais du cycle préparatoire ?
"@
$body = @{ model="qwen3:4b"; prompt=$prompt; stream=$false; options=@{ num_ctx=4096 } } | ConvertTo-Json -Depth 4
$r = Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -ContentType application/json -Body $body
"model load  : {0:N1}s" -f ($r.load_duration/1e9)
"prefill     : {0:N1}s" -f ($r.prompt_eval_duration/1e9)
"generation  : {0:N1} tok/s" -f ($r.eval_count/($r.eval_duration/1e9))
```

Acceptance targets on the i5‑1335U / 16 GB laptop: **prefill < 8 s**, **≥ 5 tok/s**, peak RAM ≤ 6 GB. Time‑to‑first‑token matters more than tok/s; if prefill is slow, reduce `top_k` to 3 or shrink `RAG_CHUNK_SIZE`.

---

## 5. Next steps (in order)

### 5.1 Fix the no‑provider vector gate (small, do first)

In `search_chunk_hits`, when `_provider_configured()` is false (hashed embeddings), do not accept a chunk on vector similarity alone — require the lexical match rule. Acceptance: "Quelle est la capitale de l’Australie ?" returns **0 citations** and the “couldn’t find an official source” reply; the six evaluation cases still pass.

### 5.2 Bring up Ollama (Path A or B above)

Acceptance: composed French/English answers with `[1]`/`[2]` citations; evaluation 3/3; no fallback message.

### 5.3 Measure retrieval with a real golden set

- Expand the 6 smoke cases to the 38‑question bank (in `C:\Users\ahmedr2\opencode-output\iit-isb-knowledge-corpus.md`, §8), each with an expected document.
- Report **recall@4** and **MRR** before/after any change; keep the numbers in the repo (`backend/tests` or a script).
- Tune `RAG_VECTOR_WEIGHT` with real embeddings (start at 0.5, try 0.4/0.6).

### 5.4 Then, and only then, Phase 2

- Conversation‑aware retrieval (question + last exchange, not the whole profile).
- Query rewrite for short/ambiguous questions.
- Optional LLM re‑ranking of the top 20 passages.

### 5.5 UI and ops

- Render `snippet` in the citation list (`app/page.tsx`) so candidates see the passage.
- Admin UI button for reindex/delete (endpoints exist, UI does not).
- Rotate the GitHub token, remove it from `.git/config`, use the credential helper.
- Local Whisper service for the existing transcription endpoint (Ollama cannot serve it).

---

## 6. Reference

**Env vars**

| Variable | Purpose | Current |
|---|---|---|
| `OPENAI_BASE_URL` | OpenAI‑compatible endpoint | unset |
| `OPENAI_API_KEY` | Enables provider chat + embeddings | unset |
| `CHAT_MODEL` | Chat model id | unset |
| `EMBEDDING_MODEL` | Embedding model id | `text-embedding-3-small` (unused without key) |
| `EMBEDDING_DIMENSIONS` | Must match the model | 1536 |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | Chunking | 800 / 120 |
| `RAG_VECTOR_WEIGHT` | Hybrid blend | 0.3 (no provider) / 0.5 (provider) |

**Endpoints added**

| Method | Path | Notes |
|---|---|---|
| POST | `/api/admin/documents/reindex` | Rebuild all chunks with the current embedding model |
| DELETE | `/api/admin/documents/{id}` | Removes document + chunks |
| POST | `/api/admin/evaluations` | Existing; now reports retrieved chunks |

**Key files**

- `backend/app/rag.py` — chunker, embeddings, hybrid search, prompts
- `backend/app/models.py` — `KnowledgeDocument`, `DocumentChunk`
- `backend/app/seed.py` — 15 programmes + 16 documents
- `backend/app/main.py` — endpoints, citations, language detection
- `backend/migrations/versions/0002_document_chunks.py`
- `backend/tests/test_workflow.py` — 7 tests
- `C:\Users\ahmedr2\opencode-output\iit-isb-knowledge-corpus.md` — sourced research + 38 questions


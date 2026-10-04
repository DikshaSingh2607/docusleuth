# DocuSleuth

DocuSleuth is an evidence-only document investigator. It starts empty: all document content, vectors, entities, conflicts, and citations come from user uploads and real provider responses.

## Current architecture

- Next.js + TypeScript + Tailwind frontend.
- FastAPI backend in a custom container.
- External PostgreSQL with `pgvector` for vectors and PostgreSQL `tsvector` full-text search.
- Real configurable embeddings and LLM providers. No local or placeholder embeddings and no simulated AI.
- Docker Compose includes a local pgvector service for development only; production uses the configured external database.

PostgreSQL full-text ranking is used for the keyword side of hybrid retrieval. It is **not exact BM25**. Retrieval combines dense vector ranking and `tsvector` ranking with reciprocal rank fusion before reranking.

## Environment

Copy `.env.example` to a local environment and provide values through protected runtime configuration in managed environments. Never commit `.env` or provider keys. The required production secrets are `DATABASE_URL`, `DATABASE_DIRECT_URL`, `OPENAI_EMBEDDINGS_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, and `APP_SESSION_SECRET`.

The privacy notice in the UI explains that documents and selected evidence are sent to the configured AI provider for extraction, embeddings, NLI, reranking, and answering as applicable.

## Run

```bash
cd frontend && npm install && npm run dev
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

The initial API health check is `GET /health`. AI-dependent routes will fail clearly until real provider configuration is present; they never return fake results.

## Tests

Tests run against real services. Provider-dependent tests are reported as blocked when required secrets or the user-provided fixture package are unavailable; the test suite never substitutes mocks for required AI behavior. The evaluation uses the user-provided `docusleuth_test_fixtures.zip` and `README_TEST_KEY.md`, including the 12 planted conflicts, controls, seven unanswerable questions, table cases, and OCR cases. Precision and recall are reported as TP/FP/FN-derived metrics.

## Deployment

The managed Webdev deployment uses the static frontend build plus the FastAPI container, with `/api/*` routed to the server and the public page routes routed to static output. The public deployment is performed only after the protected database, embeddings, and LLM secrets are configured and real build/health/smoke checks pass.


## Workflow features

Each ready document receives a provider-generated summary and strict-schema key-entity list. Workspace full-text search covers extracted text, summaries, entities, and stored evidence. Question history preserves the streamed answer, citations, confidence, and conflict context. The Evidence Board stores user pins against real chunks with optional notes. Markdown and PDF exports serialize the complete workspace investigation: documents and summaries, questions and answers, citations, confidence, conflicts, trust decisions, and Evidence Board notes.

The PDF is generated server-side from the same export model as Markdown. It is not a screenshot and it does not invent missing content. DOCX is intentionally section-cited in v1 because page-accurate rendering is not guaranteed in the container; no page numbers are fabricated.

`Delete all my data` deletes the anonymous workspace row and relies on database cascades to remove document bytes, pages, chunks and vectors, ingestion jobs, entities, summaries, conflicts, trust decisions, conversations/messages, Evidence Board pins, rate limits, and the session record. The authenticated scheduled recovery endpoint also deletes inactive anonymous workspaces after seven days.


## Public-use hardening

The API now sends CSP and defensive response headers, uses a configured CORS allowlist instead of wildcard access, applies database-backed IP/request limits, enforces upload and answer cost guards, deduplicates uploads by workspace-scoped SHA-256 hash, and serializes concurrent uploads behind a workspace row lock. Empty files, corrupt PDFs, password-protected PDFs, blank OCR images, and missing extracted text fail clearly. OCR languages are configurable with `OCR_LANGUAGES`; mixed-language text PDFs/TXT files preserve Unicode, while scanned languages require the corresponding Tesseract language data in the container. Deleted or cross-workspace source references remain 404.

## Hardening test report (measured 2026-10-04)

| Check | Result | Measured detail |
|---|---:|---|
| Backend unit/edge tests | PASS | 10 passed, 0 failed |
| Real upload-to-answer integration | BLOCKED | 1 skipped because protected real-service configuration is not available to the test process and PostgreSQL is not connected |
| Frontend TypeScript/build | PASS | `npm run typecheck` and `npm run build` completed successfully after the final hardening changes |
| API security headers/CORS/static serving | PASS | CSP, `nosniff`, referrer, permissions, allowlisted CORS, static frontend, and route manifest verified over HTTP |
| Evaluation runner | BLOCKED | Fixture package and `README_TEST_KEY.md` are not attached; no metric values emitted |
| Retrieval recall@k | NOT MEASURED | Gold retrieval labels unavailable |
| Answer groundedness | NOT MEASURED | Real upload-to-answer run blocked |
| Conflict precision/recall | NOT MEASURED | Gold conflict labels unavailable |
| Abstention accuracy | NOT MEASURED | Gold unanswerable-question labels unavailable |

The real embeddings smoke test reached the approved provider but returned HTTP 401. The API health endpoint remains available and reports `database_ready: false`; no mock embeddings, mock database, simulated OCR, or simulated LLM responses were substituted.

Run the fixture evaluation with `python3 scripts/evaluate.py`. It exits with status `2` and writes a `blocked` report when `README_TEST_KEY.md` or a supported gold-label manifest is absent; it does not print placeholder metric values.

## ALGOTHON'26 submission

See [`docs/ALGOTHON26_SUBMISSION.md`](docs/ALGOTHON26_SUBMISSION.md) for the architecture explanation, external-component disclosure, known limitations, and two-minute upload-your-own-documents demo script. The Mermaid source is [`docs/architecture.mmd`](docs/architecture.mmd), and the itemized acceptance report is [`docs/acceptance-checklist.md`](docs/acceptance-checklist.md).

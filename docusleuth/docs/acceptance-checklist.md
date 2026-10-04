# DocuSleuth ALGOTHON'26 Acceptance Checklist

Measured against the current repository on 2026-10-04. Status vocabulary: **PASS** means directly verified; **BLOCKED** means the implementation exists or the check is defined but requires unavailable real services/fixtures; **FAIL** means an observed requirement violation. No observed item is marked FAIL; blocked items are not represented as passes.

| # | Acceptance area | Status | Evidence / blocker |
|---:|---|---|---|
| 1 | Empty private workspace, secure upload pipeline, file signatures, limits, statuses, privacy, deletion, seven-day retention | BLOCKED | Code paths and unit edge cases exist; 10 unit tests pass. Real workspace/database isolation, upload persistence, deletion cascade, and retention require connected PostgreSQL. |
| 2 | Real extraction, OCR, DOCX fallback, chunking, embeddings, pgvector/tsvector, durable worker | BLOCKED | PyMuPDF, Tesseract, python-docx, chunking, and extraction edge tests pass. Real embeddings returned HTTP 401 and PostgreSQL is not connected, so indexing cannot be accepted end to end. |
| 3 | Grounded streaming Q&A, abstention, citations, source viewer, confidence, limits | BLOCKED | Routes, citation mapping, source viewer, abstention string, and cost guards are implemented. Upload-to-answer integration is skipped because PostgreSQL is not connected; no groundedness metric is claimed. |
| 4 | Entity extraction, structured comparison, NLI, false-positive filtering, conflict panel, scan cap, trust decisions | BLOCKED | Strict schemas and conflict UI/code are present. Real LLM NLI and multi-document conflict scans cannot run without the connected database/provider; fixture precision/recall is not measured. |
| 5 | Responsive three-pane investigator UI, empty states, visual direction, secrets, prompt-injection handling | PASS (static) / BLOCKED (browser acceptance) | Frontend typecheck/build passed; Preview and route manifest serve; secrets are not in source/logs. Full browser interaction and cross-session acceptance were not run against a live database. |
| 6 | Exportable project, managed routing, README/env, real-service tests, staged/final publication | BLOCKED | GitHub-ready source, Docker Compose, README, `.env.example`, route manifest, and health endpoint exist. No public deployment was claimed because real database/embedding prerequisites failed. |
| 7 | Per-document summaries, key entities, full-text search | BLOCKED | Workflow code and UI are implemented. Real summary/entity generation and search require a ready document in PostgreSQL and a valid LLM/embedding configuration. |
| 8 | Question history and Evidence Board | BLOCKED | Workspace-scoped routes, schema, UI, and export fields exist. Persistence/isolation requires connected PostgreSQL and a real Q&A run. |
| 9 | Markdown/PDF investigation export | PASS (unit) / BLOCKED (workspace export) | Empty-investigation Markdown/PDF export test passes; complete populated-workspace export requires database-backed history, conflicts, citations, and pins. |
| 10 | Public-use hardening and measured evaluation | PASS (local hardening) / BLOCKED (real evaluation) | 10 unit/edge tests pass; 1 real integration test is explicitly skipped as blocked; CSP/CORS/static headers and route manifest pass. Fixture evaluator writes `blocked` with no metrics because the requested fixture package/key is absent. |

## Measured numbers

- Backend unit/edge tests: **10 passed, 0 failed**.
- Real upload-to-answer integration: **1 skipped / BLOCKED** because external PostgreSQL is not connected.
- Frontend `npm run typecheck`: **PASS**.
- Frontend `npm run build`: **PASS**.
- API security headers, allowlisted CORS, static frontend, and route manifest: **PASS** over HTTP.
- Embeddings smoke test: **HTTP 401** from the configured provider.
- Database health: **`database_ready: false`**.
- Retrieval recall@k: **NOT MEASURED**.
- Answer groundedness: **NOT MEASURED**.
- Conflict precision/recall: **NOT MEASURED**.
- Abstention accuracy: **NOT MEASURED**.

The missing metric values are intentional. The evaluator will compute them only after the real fixture package and valid service prerequisites are supplied.

# DocuSleuth Delivery Outcomes

## 1. Empty, private workspace and secure upload pipeline
- The app starts empty with no dummy, mock, seeded, simulated, or hardcoded document data.
- Each visitor receives a private workspace through a cryptographically secure random session token without signup.
- Every database and vector query filters by `workspace_id`; a second browser session cannot see the first session's files, chunks, jobs, conflicts, messages, or trust decisions.
- Support drag-and-drop and multiple uploads for PDF text/scanned PDFs, PNG/JPG, TXT, and DOCX.
- Enforce a maximum of 25 MB per file and 20 files per workspace.
- Validate file signatures rather than trusting extensions or browser MIME values.
- Sanitize filenames, store uploads outside the web root, apply per-IP and per-session rate limits, and show friendly errors for corrupt or password-protected files.
- Show per-file states exactly as `queued`, `extracting`, `OCR`, `indexing`, `ready`, or `failed`.
- Add an in-app privacy notice stating that documents are sent to the configured AI provider.
- Add a `Delete all my data` action that removes the workspace's files, chunks, vectors, jobs, conflicts, trust decisions, messages, and session records.
- Anonymous workspaces are eligible for auto-deletion after 7 days through the authenticated scheduled sweep.

## 2. Real extraction, durable ingestion, and indexing
- Use PyMuPDF for text PDFs, Tesseract OCR with deskew/denoise for scans/images, python-docx for DOCX, and real extraction only.
- First package and validate Tesseract, PyMuPDF, python-docx, and required native dependencies in the custom Docker image; if native dependencies cannot be installed or run reliably, stop and report before switching to hosted OCR.
- Store page number, section heading, exact text offsets, and OCR confidence per chunk; retain OCR bounding boxes when available.
- If page-accurate DOCX rendering is unreliable, use section-based DOCX citations and document that limitation in the README; do not fake page numbers.
- Chunk structure-aware text at approximately 500 tokens with 10–15% overlap.
- Use real external embeddings behind a provider interface, defaulting to OpenAI `text-embedding-3-small`; no local or placeholder embeddings.
- Use external PostgreSQL with pgvector for dense retrieval and PostgreSQL `tsvector` full-text search for the keyword side, merged with reciprocal rank fusion and reranked.
- Document in the README that PostgreSQL full-text ranking is used and is not exact BM25.
- Store ingestion jobs durably in PostgreSQL and process them with an async background task inside FastAPI. The client polls job status.
- Add an authenticated scheduled callback only as a recovery sweep for stuck or failed jobs; it must not replace the primary worker.
- Missing provider configuration or provider failures show clear setup/error states and never produce fake output.

## 3. Grounded streaming Q&A and source viewer
- Provide streaming workspace-scoped chat through the configured real LLM provider.
- Answers use retrieved document chunks only and ignore instructions found inside document text.
- If evidence is missing, return exactly `I could not find this in the uploaded documents.`
- Every factual claim has numbered citations such as `[1]` and `[2]`, each mapped to a real stored chunk.
- Each citation shows file, page or documented section fallback, section heading, and the exact quoted passage.
- Clicking a citation opens the source viewer with the cited page/image and passage highlighted; PDF pages use pdf.js, images use OCR regions where available, and DOCX uses page-accurate rendering or documented section-based citations.
- Support single-document and multi-document questions without leaking another workspace's evidence.
- Enforce configurable maximum answer tokens and per-hour question limits.
- Show a confidence badge of `High`, `Medium`, `Low`, or `Not found` with a one-line reason based on retrieval scores, independent source count, OCR confidence of cited pages, and conflict presence.
- If evidence from different documents disagrees, do not choose one; show the conflict panel and both citations.

## 4. Conflict extraction, analysis, scan, and trust decisions
- During ingestion, extract structured entities for dates, amounts, names, organizations, IDs, percentages, and statuses per document and store them with document/chunk/page linkage, normalized values, confidence, and document date/version hints.
- Compare the same normalized subject and field across different documents.
- Run pairwise NLI through the real configured LLM with a strict JSON schema returning only entailment, contradiction, or neutral outcomes and validated supporting fields.
- Apply a false-positive filter that verifies both claims refer to the same subject using source-linked identifiers/names and a real classification signal where needed.
- Never auto-resolve conflicts.
- Show a `Conflict detected` panel with claims side by side, each file, page, exact quote, and document date/version hints.
- Rank workspace conflict results by severity.
- Add a `Scan workspace for conflicts` button that scans eligible pairs, batches LLM calls for cost control, caps candidate pairs per scan at 200, and clearly tells the user when the cap is hit.
- Let the user mark which source they trust and save the choice to the session/workspace without changing or deleting the underlying evidence.
- Add conflict scan, entity, NLI, false-positive, trust-decision, and recovery states to the UI with honest failure messages.

## 5. Responsive investigator interface and security
- Provide three panes: documents/sidebar and job statuses, chat/evidence, and source/conflict viewer.
- Support responsive layouts, light/dark mode, empty states with instructions, and loading skeletons tied to real state.
- Do not include fake testimonials or statistics.
- Use the approved editorial evidence-lab visual direction with amber evidence/conflict highlights and visible uncertainty.
- Keep secrets in protected environment variables only and out of code, logs, browser output, fixtures, and documentation examples.
- Verify scheduled callback identity and session/workspace authorization on every protected operation.
- Treat document text as untrusted input and prevent prompt injection from becoming instructions to the model.

## 6. Exportable project, deployment, and documentation
- Use Next.js + TypeScript + Tailwind frontend, FastAPI backend, Docker Compose for local development, external PostgreSQL/pgvector, and a custom Docker deployment.
- Serve the required `manus-routes.json` route manifest and configure static frontend plus `/api/*` container routing with an unauthenticated health endpoint.
- Request the actual database, embeddings, and LLM secrets through protected configuration immediately after the skeleton and health endpoint work; do not request or accept them in chat text.
- Deploy a first public version once grounded Q&A with citations works, before conflict detection, to surface platform/container issues early; deploy again after the complete feature set.
- Provide a GitHub-ready repository, README with setup/env/run/test/deploy/architecture instructions, `.env.example` with variable names only, and a short real test report.
- Use the user-provided `docusleuth_test_fixtures.zip` and `README_TEST_KEY.md` when attached; do not generate substitute fixtures. Keep fixtures under `/tests/fixtures` and never load them as app data.
- Run tests against real services and report pass/fail or blocked honestly for mixed-file upload, grounded citations/highlighting, multi-document Q&A, abstention, session isolation, planted contradictions, false-positive controls, trust persistence, conflict scan ranking/cap messaging, deletion/retention, and recovery.
- Compute precision and recall from the fixture gold labels, including TP/FP/FN counts for the 12 planted conflicts, controls that must not be flagged, seven unanswerable questions, table cases, and OCR cases.
- Provide the final public HTTPS URL only after successful publication is confirmed; do not claim deployment from a preview or checkpoint alone.


## 7. Document workflow intelligence
- For every successfully ingested document, generate a summary from that document's extracted text and a key-entity list for dates, amounts, names, organizations, IDs, percentages, and statuses through the configured real LLM with strict JSON output.
- Display the summary and key entities per document and show a clear provider/error state when generation fails; never show sample, mock, placeholder, or simulated summaries/entities.
- Provide full-text search across the workspace's stored document text, generated summaries, entity names/values, citations, and user-pinned findings; every result is workspace-scoped and links to its stored document/chunk/source context.
- Document that PostgreSQL `tsvector` ranking is used for full-text search and is not exact BM25.

## 8. Investigation history and Evidence Board
- Persist question history per anonymous workspace with the question, streamed answer, citations, confidence badge/reason, conflict context, and timestamp; another workspace cannot read it.
- Provide a history view that can reopen a prior answer's citations/source context without fabricating or changing the stored answer.
- Provide an Evidence Board where the user can pin a finding/citation with a note, edit the note, unpin it, and reopen the stored source; pins store the real chunk/citation, quote, question context, confidence, and note.
- Evidence Board content is workspace-scoped, contains no sample findings, and is deleted by `Delete all my data` and the seven-day retention sweep.

## 9. Investigation export
- Export the whole current investigation as Markdown and PDF, including questions, answers, citations with file/page-or-section/quote, confidence and reasons, conflicts with both claims, trust decisions, and Evidence Board notes.
- Generate both formats from the same workspace-scoped export model using a real Markdown/PDF renderer; do not create screenshots or invented content.
- Export errors are shown honestly and exports cannot include another workspace's data or provider secrets.


## 10. Public-use hardening and measured evaluation
- Add CSP/security headers without using frame-ancestors `self` or `none`, and restrict CORS to configured origins, methods, and headers.
- Add database-backed request limits for uploads and questions, maximum upload bytes/file count, maximum answer tokens/characters, and conflict candidate caps; return explicit 429/413 errors.
- Reject empty files, invalid/corrupt PDFs, password-protected PDFs, and images with no OCR text with friendly failed states; support configurable Tesseract languages for mixed-language scans.
- Deduplicate uploads by workspace-scoped SHA-256 content hash and make concurrent uploads safe through workspace locking and a unique constraint.
- Keep deleted-document references and cross-workspace references at 404; never return stale file/chunk/source content.
- Add unit tests for chunking, citation mapping, and tenant isolation; add real extraction edge-case tests; add an integration upload-to-answer test that is explicitly BLOCKED rather than mocked when external services are unavailable.
- Add an evaluation script that reports retrieval recall@k, answer groundedness, conflict precision/recall, and abstention accuracy only from real fixture gold labels; report TP/FP/FN and leave metrics absent/blocked when fixtures or services are unavailable.
- Run all checks and put only measured pass/fail/blocked counts and real metrics in the README; never invent values.

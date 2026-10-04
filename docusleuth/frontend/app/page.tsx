'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Check, ChevronRight, FileText, Fingerprint, Loader2, Moon, Search, ShieldCheck, Trash2, UploadCloud, X } from 'lucide-react';
import { apiFetch, apiUrl, Citation, Conflict, DocumentRecord } from '@/lib/api';
import WorkflowDrawer from '@/components/WorkflowDrawer';

type Confidence = { level: 'High' | 'Medium' | 'Low' | 'Not found'; reason: string };
type SourcePage = { page_number: number | null; section_heading: string | null; text_content: string; ocr_confidence: number | null };

type StreamMeta = { citations: Citation[]; conflicts: Conflict[]; confidence: Confidence };
type Summary = { document_id: string; filename: string; status: string; summary: string | null; key_entities: Array<{ entity_type: string; subject: string; value: string }> | null; error_message: string | null };
type SearchResult = { result_type: string; result_id: string; document_id: string; filename: string; page_number: number | null; section_heading: string | null; quote: string; score: number };
type HistoryItem = { id: string; question: string | null; answer: string | null; confidence: Confidence | null; citations: Citation[] | null; created_at: string };
type Pin = { id: string; filename: string; page_number: number | null; section_heading: string | null; quote: string; note: string; question: string | null };

const statusStyle: Record<string, string> = {
  queued: 'bg-ink/5 text-ink/55', extracting: 'bg-amber/10 text-amber-800', OCR: 'bg-amber/15 text-amber-900', indexing: 'bg-sky-50 text-sky-700', ready: 'bg-emerald-50 text-emerald-700', failed: 'bg-red-50 text-red-700'
};

function Status({ value }: { value: string }) {
  return <span className={`rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusStyle[value] ?? statusStyle.queued}`}>{value}</span>;
}

function ConfidenceBadge({ confidence }: { confidence: Confidence | null }) {
  if (!confidence) return null;
  const tone = confidence.level === 'High' ? 'bg-emerald-50 text-emerald-700' : confidence.level === 'Medium' ? 'bg-amber/10 text-amber-900' : confidence.level === 'Low' ? 'bg-red-50 text-red-700' : 'bg-ink/5 text-ink/55';
  return <div className={`inline-flex max-w-full items-center gap-2 rounded-full px-3 py-1.5 text-xs ${tone}`}><span className="font-bold">{confidence.level}</span><span className="truncate">{confidence.reason}</span></div>;
}

function HighlightedText({ text, quote }: { text: string; quote: string }) {
  if (!quote || !text.toLowerCase().includes(quote.toLowerCase())) return <p className="whitespace-pre-wrap text-sm leading-7 text-ink/75">{text}</p>;
  const start = text.toLowerCase().indexOf(quote.toLowerCase());
  return <p className="whitespace-pre-wrap text-sm leading-7 text-ink/75">{text.slice(0, start)}<mark className="rounded bg-amber/30 px-1 text-ink">{text.slice(start, start + quote.length)}</mark>{text.slice(start + quote.length)}</p>;
}

function PdfPage({ source, page }: { source: string; page: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [renderError, setRenderError] = useState('');
  useEffect(() => {
    let cancelled = false;
    void import('pdfjs-dist/legacy/build/pdf.mjs').then(async (pdfjs) => {
      const document = await pdfjs.getDocument({ url: source, useWorkerFetch: false }).promise;
      const pdfPage = await document.getPage(page);
      const viewport = pdfPage.getViewport({ scale: 1.25 });
      const canvas = canvasRef.current;
      if (!canvas || cancelled) return;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await pdfPage.render({ canvas, canvasContext: canvas.getContext('2d')!, viewport }).promise;
    }).catch((error: unknown) => { if (!cancelled) setRenderError(error instanceof Error ? error.message : 'PDF page could not be rendered.'); });
    return () => { cancelled = true; };
  }, [source, page]);
  return <div className="overflow-auto rounded-lg border border-ink/10 bg-ink/5 p-2">{renderError ? <p className="p-3 text-xs text-red-700">{renderError}</p> : <canvas ref={canvasRef} className="mx-auto max-w-full" aria-label={`PDF page ${page}`} />}</div>;
}

export default function Home() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [sourcePages, setSourcePages] = useState<SourcePage[]>([]);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [workflowTab, setWorkflowTab] = useState<'summary' | 'search' | 'history' | 'board'>('summary');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryDocId, setSummaryDocId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [pins, setPins] = useState<Pin[]>([]);
  const [busy, setBusy] = useState(false);
  const [scanBusy, setScanBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [docs, nextConflicts] = await Promise.all([
        apiFetch<DocumentRecord[]>('/api/documents'),
        apiFetch<Conflict[]>('/api/conflicts'),
      ]);
      setDocuments(docs);
      setConflicts(nextConflicts);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load this workspace.');
    }
  }, []);

  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 2500); return () => window.clearInterval(timer); }, [refresh]);

  const readyDocuments = useMemo(() => documents.filter((doc) => doc.status === 'ready').length, [documents]);

  const openSummary = async (documentId: string) => {
    setWorkflowTab('summary'); setSummaryDocId(documentId); setSummary(null);
    try { setSummary(await apiFetch<Summary>(`/api/documents/${documentId}/summary`)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Summary could not be loaded.'); }
  };

  const runSearch = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!searchQuery.trim()) return;
    try { setSearchResults(await apiFetch<SearchResult[]>(`/api/search?q=${encodeURIComponent(searchQuery.trim())}`)); setWorkflowTab('search'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Search failed.'); }
  };

  const loadHistory = async () => {
    try { setHistory(await apiFetch<HistoryItem[]>('/api/history')); setWorkflowTab('history'); }
    catch (err) { setError(err instanceof Error ? err.message : 'History could not be loaded.'); }
  };

  const loadPins = async () => {
    try { setPins(await apiFetch<Pin[]>('/api/pins')); setWorkflowTab('board'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Evidence Board could not be loaded.'); }
  };

  const pinCitation = async (citation: Citation) => {
    const note = window.prompt('Add a note to this evidence pin (optional):', '') ?? '';
    try { await apiFetch('/api/pins', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chunk_id: citation.chunk_id, question, confidence, note }) }); await loadPins(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Evidence could not be pinned.'); }
  };

  const removePin = async (pinId: string) => {
    try { await apiFetch(`/api/pins/${pinId}`, { method: 'DELETE' }); await loadPins(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Evidence pin could not be removed.'); }
  };

  const openHistory = async (item: HistoryItem) => {
    try {
      const detail = await apiFetch<{ messages: Array<{ role: string; content: string; citations: Citation[] | null; confidence: Confidence | null }> }>(`/api/history/${item.id}`);
      const userMessage = detail.messages.find((message) => message.role === 'user');
      const assistantMessage = [...detail.messages].reverse().find((message) => message.role === 'assistant');
      setQuestion(userMessage?.content ?? ''); setAnswer(assistantMessage?.content ?? ''); setCitations(assistantMessage?.citations ?? []); setConfidence(assistantMessage?.confidence ?? null); setWorkflowTab('history');
    } catch (err) { setError(err instanceof Error ? err.message : 'History item could not be opened.'); }
  };

  const upload = async (files: FileList | File[]) => {
    if (!files.length) return;
    setBusy(true); setError('');
    const form = new FormData();
    Array.from(files).forEach((file) => form.append('files', file));
    try { await apiFetch('/api/upload', { method: 'POST', body: form }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Upload failed.'); }
    finally { setBusy(false); }
  };

  const selectCitation = async (citation: Citation) => {
    setSelectedCitation(citation); setSourceLoading(true); setSourcePages([]);
    try { setSourcePages(await apiFetch<SourcePage[]>(`/api/documents/${citation.document_id}/pages`)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Source could not be opened.'); }
    finally { setSourceLoading(false); }
  };

  const ask = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true); setAnswer(''); setCitations([]); setConfidence(null); setError('');
    try {
      const response = await fetch(apiUrl('/api/chat/stream'), { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
      if (!response.ok || !response.body) throw new Error((await response.text()) || `Chat failed with HTTP ${response.status}`);
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      const consume = (block: string) => {
        const lines = block.split('\n'); let event = 'message'; let data = '';
        lines.forEach((line) => { if (line.startsWith('event: ')) event = line.slice(7); if (line.startsWith('data: ')) data += line.slice(6); });
        if (!data) return;
        const payload = JSON.parse(data) as { citations?: Citation[]; conflicts?: Conflict[]; confidence?: Confidence; text?: string; message?: string };
        if (event === 'meta') { setCitations(payload.citations ?? []); setConflicts(payload.conflicts ?? []); setConfidence(payload.confidence ?? null); }
        if (event === 'chunk') setAnswer((current) => current + (payload.text ?? ''));
        if (event === 'error') setError(payload.message ?? 'The provider returned an error.');
        if (event === 'done') setConfidence(payload.confidence ?? null);
      };
      while (true) { const { value, done } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const blocks = buffer.split('\n\n'); buffer = blocks.pop() ?? ''; blocks.forEach(consume); }
      if (buffer.trim()) consume(buffer);
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : 'The question could not be answered.'); }
    finally { setBusy(false); }
  };

  const scan = async () => {
    setScanBusy(true); setError('');
    try {
      const scanResult = await apiFetch<{ scan_id: string }>('/api/conflicts/scan', { method: 'POST' });
      for (let attempt = 0; attempt < 60; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const status = await apiFetch<{ status: string; cap_hit: boolean; candidate_count: number; error_message: string | null }>(`/api/conflicts/scans/${scanResult.scan_id}`);
        if (status.status === 'ready') { if (status.cap_hit) setError(`Conflict scan reached the ${status.candidate_count}-candidate cap; results are not exhaustive.`); await refresh(); break; }
        if (status.status === 'failed') throw new Error(status.error_message ?? 'Conflict scan failed.');
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Conflict scan failed.'); }
    finally { setScanBusy(false); }
  };

  const trust = async (conflictId: string, claimId: string) => {
    try { await apiFetch(`/api/conflicts/${conflictId}/trust`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ claim_id: claimId }) }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Trust decision could not be saved.'); }
  };

  const deleteAll = async () => {
    if (!window.confirm('Delete all documents, evidence, conflicts, messages, and this private session? This cannot be undone.')) return;
    setBusy(true);
    try { await apiFetch('/api/data', { method: 'DELETE' }); window.location.reload(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Deletion failed.'); setBusy(false); }
  };

  return (
    <main className="min-h-screen bg-paper">
      <header className="border-b border-ink/10 bg-paper/90 px-5 py-4 backdrop-blur md:px-8">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between">
          <div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-full border-2 border-amber text-amber"><Search size={18} strokeWidth={2.5} /></div><div><div className="serif text-xl font-semibold tracking-tight">DocuSleuth</div><div className="text-[10px] uppercase tracking-[0.22em] text-ink/50">Intelligent document investigator</div></div></div>
          <div className="flex items-center gap-3 text-xs text-ink/55"><span className="hidden items-center gap-2 md:flex"><ShieldCheck size={15} /> Private workspace · {readyDocuments} ready</span><button className="rounded-full p-2 hover:bg-ink/5" aria-label="Toggle dark mode"><Moon size={16} /></button><button onClick={() => setPrivacyOpen(true)} className="hidden rounded-full border border-ink/15 px-3 py-1.5 text-[11px] font-semibold md:block">Privacy</button></div>
        </div>
      </header>
      {error && <div className="mx-auto flex max-w-[1600px] items-center gap-2 border-x border-b border-red-200 bg-red-50 px-5 py-3 text-sm text-red-800"><AlertTriangle size={16} /><span className="flex-1">{error}</span><button onClick={() => setError('')}><X size={16} /></button></div>}
      <section className="mx-auto grid min-h-[calc(100vh-74px)] max-w-[1600px] grid-cols-1 border-x border-ink/10 lg:grid-cols-[270px_minmax(0,1fr)_400px]">
        <aside className="border-b border-ink/10 p-5 lg:border-b-0 lg:border-r">
          <div className="mb-5 flex items-center justify-between"><h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/55">Case files</h2><span className="rounded bg-mist px-2 py-1 text-[10px] text-ink/50">{documents.length}/20</span></div>
          <label onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files); }} className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed p-4 text-center transition ${dragging ? 'border-amber bg-amber/10' : 'border-ink/20 bg-white/40 hover:bg-amber/5'}`}><UploadCloud className="mb-2 text-amber-700" size={22} /><span className="text-xs font-semibold">Add source files</span><span className="mt-1 text-[10px] leading-4 text-ink/50">PDF, image, TXT, DOCX · 25 MB each</span><input ref={inputRef} className="sr-only" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt,.docx" onChange={(event) => { if (event.target.files) void upload(event.target.files); }} /></label>
          <div className="mt-5 space-y-2">{documents.map((doc) => <div key={doc.id} className="rounded-lg border border-ink/10 bg-white/45 p-3"><div className="flex items-start gap-2"><FileText size={15} className="mt-0.5 shrink-0 text-ink/45" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium" title={doc.filename}>{doc.filename}</p><div className="mt-2 flex items-center justify-between gap-2"><Status value={doc.status} />{doc.error_message && <span className="truncate text-[10px] text-red-700" title={doc.error_message}>{doc.error_message}</span>}</div></div></div></div>)}</div>
          {documents.length === 0 && <div className="mt-5 rounded-xl border border-dashed border-ink/15 p-4 text-center"><p className="text-xs font-medium">No documents yet</p><p className="mt-2 text-[11px] leading-4 text-ink/50">Upload source material to open a private investigation workspace.</p></div>}
          <div className="mt-7 border-t border-ink/10 pt-5 text-[11px] leading-5 text-ink/55"><p className="font-semibold text-ink/75">Evidence rules</p><p className="mt-2">Answers use retrieved chunks only. If sources disagree, DocuSleuth shows both claims.</p><button onClick={deleteAll} disabled={busy} className="mt-4 flex items-center gap-2 text-red-700 hover:underline disabled:opacity-50"><Trash2 size={13} /> Delete all my data</button></div>
        </aside>
        <section className="flex min-h-[640px] flex-col bg-white/35 p-5 md:p-8">
          <div className="mb-6 flex items-center justify-between"><div><div className="mb-2 inline-flex items-center gap-2 rounded-full border border-amber/35 bg-amber/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-900"><Fingerprint size={14} /> Evidence desk</div><h1 className="serif text-3xl tracking-tight md:text-4xl">Ask the files, <span className="text-amber-700">not the model.</span></h1></div><button onClick={scan} disabled={scanBusy || documents.length < 2} className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-white/60 px-3 py-2 text-xs font-semibold hover:border-amber disabled:cursor-not-allowed disabled:opacity-45">{scanBusy ? <Loader2 className="animate-spin" size={14} /> : <AlertTriangle size={14} />} Scan conflicts</button></div>
          {answer ? <div className="mb-5 rounded-2xl border border-ink/10 bg-white/75 p-5 shadow-sm"><div className="flex items-center justify-between gap-3"><div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ink/45">Investigation note</div><ConfidenceBadge confidence={confidence} /></div><div className="mt-4 whitespace-pre-wrap text-sm leading-7 text-ink/80">{answer}</div>{citations.length > 0 && <div className="mt-5 border-t border-ink/10 pt-4"><p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.17em] text-ink/45">Cited evidence</p><div className="flex flex-wrap gap-2">{citations.map((citation) => <button key={citation.number} onClick={() => void selectCitation(citation)} className="inline-flex max-w-full items-center gap-2 rounded-lg border border-amber/25 bg-amber/5 px-3 py-2 text-left text-xs hover:bg-amber/15"><span className="font-bold text-amber-800">[{citation.number}]</span><span className="max-w-[220px] truncate">{citation.filename} · {citation.page ? `p. ${citation.page}` : citation.section || 'section'}</span><ChevronRight size={13} className="shrink-0 text-ink/35" /></button>)}</div></div>}</div> : <div className="flex flex-1 flex-col items-center justify-center py-16 text-center"><div className="mb-5 grid h-16 w-16 place-items-center rounded-full border border-amber/35 bg-amber/10 text-amber-800"><FileText size={28} /></div><h2 className="serif text-3xl tracking-tight">Start with the record</h2><p className="mt-3 max-w-md text-sm leading-6 text-ink/55">Upload contracts, reports, scans, or notes. Once a file is ready, ask a question and inspect the exact passage behind each claim.</p></div>}
          <form onSubmit={ask} className="mt-auto rounded-2xl border border-ink/15 bg-white/80 p-3 shadow-sm"><textarea value={question} onChange={(event) => setQuestion(event.target.value)} disabled={busy || readyDocuments === 0} placeholder={readyDocuments ? 'Ask a question grounded in your documents…' : 'Upload and index a document to begin…'} rows={3} className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-ink/35 disabled:cursor-not-allowed" /><div className="flex items-center justify-between gap-3 border-t border-ink/10 px-2 pt-3"><span className="text-[10px] text-ink/40">Every factual claim must cite a stored chunk.</span><button disabled={busy || readyDocuments === 0 || !question.trim()} className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-xs font-semibold text-paper hover:bg-ink/85 disabled:cursor-not-allowed disabled:opacity-40">{busy ? <Loader2 className="animate-spin" size={14} /> : <Search size={14} />} Investigate</button></div></form>
          <WorkflowDrawer documents={documents} question={question} confidence={confidence} citations={citations} onSelectCitation={(citation) => void selectCitation(citation)} />
        </section>
        <aside className="border-t border-ink/10 p-5 lg:border-l lg:border-t-0">
          <div className="mb-5 flex items-center justify-between"><h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/55">Source viewer</h2><span className="text-[10px] uppercase tracking-[0.16em] text-ink/40">{selectedCitation ? 'Inspecting' : 'Awaiting source'}</span></div>
          {selectedCitation ? <div className="space-y-4"><div className="rounded-xl border border-amber/30 bg-amber/5 p-4"><div className="flex items-start gap-3"><FileText size={17} className="mt-0.5 text-amber-800" /><div className="min-w-0"><p className="truncate text-sm font-semibold">{selectedCitation.filename}</p><p className="mt-1 text-xs text-ink/55">{selectedCitation.page ? `Page ${selectedCitation.page}` : 'Section-based citation'}{selectedCitation.section ? ` · ${selectedCitation.section}` : ''}</p>{selectedCitation.date_hint || selectedCitation.version_hint ? <p className="mt-2 text-[11px] text-ink/55">{selectedCitation.date_hint ?? ''}{selectedCitation.version_hint ? ` · ${selectedCitation.version_hint}` : ''}</p> : null}</div></div></div>{selectedCitation.page && selectedCitation.filename.toLowerCase().endsWith('.pdf') && <PdfPage source={apiUrl(`/api/documents/${selectedCitation.document_id}/content`)} page={selectedCitation.page} />}{selectedCitation.filename.toLowerCase().match(/\.(png|jpe?g)$/) && <img src={apiUrl(`/api/documents/${selectedCitation.document_id}/content`)} alt={`Source ${selectedCitation.filename}`} className="max-h-72 w-full rounded-lg border border-ink/10 object-contain" />}{sourceLoading ? <div className="flex items-center gap-2 text-sm text-ink/50"><Loader2 className="animate-spin" size={15} /> Loading source…</div> : <div className="rounded-xl border border-ink/10 bg-white/55 p-4">{sourcePages.map((page, index) => <div key={`${page.page_number}-${index}`} className="mb-5 last:mb-0"><p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink/45">{page.page_number ? `Page ${page.page_number}` : page.section_heading || 'Document section'}{page.ocr_confidence !== null ? ` · OCR ${Math.round(page.ocr_confidence * 100)}%` : ''}</p><HighlightedText text={page.text_content} quote={selectedCitation.quote} /></div>)}</div>}{selectedCitation.document_id && <a className="inline-flex text-xs font-semibold text-amber-800 hover:underline" href={apiUrl(`/api/documents/${selectedCitation.document_id}/content`)} target="_blank" rel="noreferrer">Open original source <ChevronRight size={13} /></a>}<button onClick={() => setSelectedCitation(null)} className="block text-xs text-ink/45 hover:underline">Close source</button></div> : <div className="rounded-xl border border-ink/10 bg-white/45 p-5"><div className="h-2 w-24 rounded bg-mist" /><div className="mt-5 space-y-3"><div className="h-2 w-full rounded bg-mist/80" /><div className="h-2 w-11/12 rounded bg-mist/80" /><div className="h-2 w-4/5 rounded bg-mist/80" /></div><p className="mt-8 text-xs leading-5 text-ink/50">Citations open here with the source context and quoted passage highlighted.</p></div>}
          {conflicts.length > 0 && <div className="mt-6 border-t border-ink/10 pt-5"><div className="mb-3 flex items-center justify-between"><h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-red-800">Conflict detected</h3><span className="rounded bg-red-50 px-2 py-1 text-[10px] text-red-700">{conflicts.length}</span></div><div className="space-y-3">{conflicts.map((conflict) => <div key={conflict.id} className="rounded-xl border border-red-200 bg-red-50/50 p-3"><div className="flex items-start justify-between gap-2"><div><p className="text-xs font-semibold">{conflict.subject}</p><p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-red-700">{conflict.field_type} · {conflict.severity} severity</p></div><AlertTriangle size={15} className="shrink-0 text-red-700" /></div><div className="mt-3 grid gap-2">{conflict.claims.map((claim) => <div key={claim.claim_id} className="rounded-lg border border-red-200/80 bg-white/65 p-3"><p className="text-[10px] font-semibold text-ink/60">{claim.filename} · {claim.page_number ? `p. ${claim.page_number}` : claim.section_heading || 'section'}</p><p className="mt-1 text-xs font-medium">{claim.claim_value}</p><p className="mt-2 text-[11px] leading-5 text-ink/65">“{claim.quote}”</p><button onClick={() => void trust(conflict.id, claim.claim_id)} className="mt-2 inline-flex items-center gap-1 text-[10px] font-semibold text-amber-800 hover:underline"><Check size={12} /> Mark this source trusted for this session</button></div>)}</div>{conflict.reason && <p className="mt-3 text-[10px] leading-4 text-ink/55">NLI: {conflict.reason}</p>}</div>)}</div></div>}
        </aside>
      </section>
      {privacyOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-ink/35 p-5" role="dialog" aria-modal="true"><div className="max-w-lg rounded-2xl border border-ink/10 bg-paper p-6 shadow-xl"><div className="flex items-start justify-between gap-4"><div><h2 className="serif text-2xl">Privacy, in plain terms</h2><p className="mt-3 text-sm leading-6 text-ink/70">Your workspace is private to this anonymous session. Uploaded documents and selected evidence are sent to the configured AI provider for extraction, embeddings, conflict analysis, reranking, and answering. Document text is treated as untrusted data, not instructions.</p><p className="mt-3 text-sm leading-6 text-ink/70">Delete all my data removes the workspace records and stored document bytes. Anonymous workspaces are also scheduled for deletion after 7 days of inactivity.</p></div><button onClick={() => setPrivacyOpen(false)} aria-label="Close privacy notice"><X size={18} /></button></div><button onClick={() => setPrivacyOpen(false)} className="mt-6 rounded-full bg-ink px-4 py-2 text-xs font-semibold text-paper">Understood</button></div></div>}
    </main>
  );
}

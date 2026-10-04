'use client';

import { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { apiFetch, apiUrl, Citation, DocumentRecord } from '@/lib/api';

type Confidence = { level: 'High' | 'Medium' | 'Low' | 'Not found'; reason: string };
type Summary = { document_id: string; filename: string; status: string; summary: string | null; key_entities: Array<{ entity_type: string; subject: string; value: string }> | null; error_message: string | null };
type SearchResult = { result_type: string; result_id: string; document_id: string; filename: string; page_number: number | null; section_heading: string | null; quote: string; score: number };
type HistoryItem = { id: string; question: string | null; answer: string | null; confidence: Confidence | null; citations: Citation[] | null; created_at: string };
type Pin = { id: string; filename: string; page_number: number | null; section_heading: string | null; quote: string; note: string; question: string | null };

type Props = { documents: DocumentRecord[]; question: string; confidence: Confidence | null; citations: Citation[]; onSelectCitation: (citation: Citation) => void };

export default function WorkflowDrawer({ documents, question, confidence, citations, onSelectCitation }: Props) {
  const [tab, setTab] = useState<'summary' | 'search' | 'history' | 'board'>('summary');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [pins, setPins] = useState<Pin[]>([]);

  const loadHistory = async () => setHistory(await apiFetch<HistoryItem[]>('/api/history'));
  const loadPins = async () => setPins(await apiFetch<Pin[]>('/api/pins'));
  const selectTab = (next: typeof tab) => { setTab(next); if (next === 'history') void loadHistory(); if (next === 'board') void loadPins(); };
  const search = async (event: React.FormEvent) => { event.preventDefault(); if (query.trim()) setResults(await apiFetch<SearchResult[]>(`/api/search?q=${encodeURIComponent(query.trim())}`)); };
  const openSummary = async (id: string) => setSummary(await apiFetch<Summary>(`/api/documents/${id}/summary`));
  const openHistory = async (item: HistoryItem) => {
    const detail = await apiFetch<{ messages: Array<{ role: string; content: string; citations: Citation[] | null; confidence: Confidence | null }> }>(`/api/history/${item.id}`);
    const assistant = [...detail.messages].reverse().find((message) => message.role === 'assistant');
    if (assistant?.citations?.[0]) onSelectCitation(assistant.citations[0]);
  };
  const pin = async (citation: Citation) => {
    const note = window.prompt('Add a note to this evidence pin (optional):', '') ?? '';
    await apiFetch('/api/pins', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chunk_id: citation.chunk_id, question, confidence, note }) });
    await loadPins(); setTab('board');
  };
  const removePin = async (id: string) => { await apiFetch(`/api/pins/${id}`, { method: 'DELETE' }); await loadPins(); };

  useEffect(() => { if (documents.length === 1 && !summary) void openSummary(documents[0].id); }, [documents, summary]);

  return <section className="mt-6 rounded-2xl border border-ink/10 bg-white/55 p-4">
    <div className="flex flex-wrap items-center gap-2 border-b border-ink/10 pb-3">
      {([['summary', 'Summaries'], ['search', 'Search'], ['history', 'History'], ['board', 'Evidence Board']] as const).map(([key, label]) => <button key={key} onClick={() => selectTab(key)} className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${tab === key ? 'bg-ink text-paper' : 'text-ink/55 hover:bg-ink/5'}`}>{label}</button>)}
      <span className="ml-auto flex gap-2"><a href={apiUrl('/api/export/markdown')} className="rounded-full border border-ink/15 px-3 py-1.5 text-[11px] font-semibold hover:border-amber">Export MD</a><a href={apiUrl('/api/export/pdf')} className="rounded-full border border-ink/15 px-3 py-1.5 text-[11px] font-semibold hover:border-amber">Export PDF</a></span>
    </div>
    {tab === 'summary' && <div className="pt-4"><div className="mb-3 flex flex-wrap gap-2">{documents.filter((doc) => doc.status === 'ready').map((doc) => <button key={doc.id} onClick={() => void openSummary(doc.id)} className="rounded-lg border border-ink/10 bg-white/50 px-3 py-2 text-left text-xs hover:border-amber">{doc.filename}</button>)}</div>{summary ? <div className="rounded-xl border border-ink/10 bg-white/65 p-4"><p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink/45">{summary.filename} · {summary.status}</p>{summary.error_message ? <p className="mt-3 text-xs text-red-700">{summary.error_message}</p> : <><p className="mt-3 text-sm leading-6 text-ink/75">{summary.summary || 'No summary returned by the configured provider.'}</p><div className="mt-4 flex flex-wrap gap-2">{(summary.key_entities ?? []).map((entity, index) => <span key={`${entity.subject}-${index}`} className="rounded-full bg-amber/10 px-2.5 py-1 text-[11px] text-amber-900">{entity.subject}: {entity.value}</span>)}</div></>}</div> : <p className="pt-2 text-xs leading-5 text-ink/50">Choose a ready document to inspect its provider-generated summary and key entities.</p>}</div>}
    {tab === 'search' && <div className="pt-4"><form onSubmit={search} className="flex gap-2"><input value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-ink/15 bg-white/70 px-3 py-2 text-xs outline-none focus:border-amber" placeholder="Search stored text, summaries, entities…" /><button className="rounded-lg bg-ink px-3 py-2 text-xs font-semibold text-paper">Search</button></form><div className="mt-3 space-y-2">{results.map((result) => <button key={`${result.result_type}-${result.result_id}`} onClick={() => { const citation = citations.find((item) => item.chunk_id === result.result_id); if (citation) onSelectCitation(citation); }} className="block w-full rounded-lg border border-ink/10 bg-white/55 p-3 text-left hover:border-amber"><div className="flex items-center justify-between gap-2"><span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink/45">{result.result_type} · {result.filename}</span><span className="text-[10px] text-ink/35">{result.page_number ? `p. ${result.page_number}` : result.section_heading || 'document'}</span></div><p className="mt-1 text-xs leading-5 text-ink/70">{result.quote}</p></button>)}</div></div>}
    {tab === 'history' && <div className="space-y-2 pt-4">{history.map((item) => <button key={item.id} onClick={() => void openHistory(item)} className="block w-full rounded-lg border border-ink/10 bg-white/55 p-3 text-left hover:border-amber"><p className="truncate text-xs font-semibold">{item.question || 'Untitled question'}</p><p className="mt-1 line-clamp-2 text-[11px] leading-5 text-ink/60">{item.answer || 'No saved answer'}</p><p className="mt-2 text-[10px] text-ink/40">{new Date(item.created_at).toLocaleString()}</p></button>)}{history.length === 0 && <p className="pt-2 text-xs text-ink/50">No questions have been saved in this workspace.</p>}</div>}
    {tab === 'board' && <div className="space-y-2 pt-4">{pins.map((item) => <div key={item.id} className="rounded-lg border border-ink/10 bg-white/55 p-3"><div className="flex items-start justify-between gap-2"><p className="text-xs font-semibold">{item.filename} · {item.page_number ? `p. ${item.page_number}` : item.section_heading || 'section'}</p><button onClick={() => void removePin(item.id)} className="text-ink/35 hover:text-red-700"><Trash2 size={14} /></button></div><p className="mt-2 text-[11px] leading-5 text-ink/65">“{item.quote}”</p>{item.note && <p className="mt-2 border-l-2 border-amber pl-2 text-[11px] leading-5 text-ink/70">{item.note}</p>}</div>)}{pins.length === 0 && <p className="pt-2 text-xs text-ink/50">Pin a citation from an answer to build this board.</p>}</div>}
    {citations.length > 0 && <div className="mt-4 border-t border-ink/10 pt-3"><p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink/45">Pin current citations</p><div className="flex flex-wrap gap-2">{citations.map((citation) => <button key={citation.number} onClick={() => void pin(citation)} className="rounded-lg border border-amber/25 bg-amber/5 px-3 py-1.5 text-[11px] text-amber-900 hover:bg-amber/15">Pin [{citation.number}]</button>)}</div></div>}
  </section>;
}

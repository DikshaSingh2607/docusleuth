export const apiUrl = (path: string) => `${process.env.NEXT_PUBLIC_API_ORIGIN ?? ''}${path}`;

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { ...init, credentials: 'include' });
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!response.ok) {
    const detail = typeof body === 'object' && body && 'detail' in body ? String((body as { detail: unknown }).detail) : text;
    throw new Error(detail || `Request failed with HTTP ${response.status}`);
  }
  return body as T;
}

export type Citation = {
  number: number;
  chunk_id: string;
  document_id: string;
  filename: string;
  page: number | null;
  section: string | null;
  quote: string;
  ocr_confidence: number | null;
  date_hint: string | null;
  version_hint: string | null;
  section_citation_only: boolean;
};

export type DocumentRecord = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  error_message: string | null;
  page_count?: number;
  chunk_count?: number;
  section_citation_only?: boolean;
};

export type Conflict = {
  id: string;
  subject: string;
  field_type: string;
  severity: 'high' | 'medium' | 'low';
  reason: string | null;
  claims: Array<{
    claim_id: string;
    document_id: string;
    filename: string;
    page_number: number | null;
    section_heading: string | null;
    quote: string;
    claim_value: string;
    document_date_hint: string | null;
    version_hint: string | null;
  }>;
};

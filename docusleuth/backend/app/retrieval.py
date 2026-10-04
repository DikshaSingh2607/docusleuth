from __future__ import annotations

from .db import db
from .providers import embed_texts, rerank


def vector_literal(vector: list[float]) -> str:
    return '[' + ','.join(f'{value:.8f}' for value in vector) + ']'


async def retrieve(workspace_id: str, question: str, limit: int = 12) -> list[dict]:
    vector = vector_literal((await embed_texts([question]))[0])
    dense = await db.fetch(
        '''
        SELECT c.id, c.document_id, c.page_id, c.text_content, c.page_number, c.section_heading,
               c.ocr_confidence, d.filename, d.document_date_hint, d.version_hint,
               d.section_citation_only, 1 - (c.embedding <=> $1::vector) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.workspace_id = $2 AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> $1::vector LIMIT $3
        ''',
        vector,
        workspace_id,
        limit,
    )
    keyword = await db.fetch(
        '''
        SELECT c.id, c.document_id, c.page_id, c.text_content, c.page_number, c.section_heading,
               c.ocr_confidence, d.filename, d.document_date_hint, d.version_hint,
               d.section_citation_only,
               ts_rank_cd(c.search_vector, plainto_tsquery('simple', $1)) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.workspace_id = $2
        ORDER BY ts_rank_cd(c.search_vector, plainto_tsquery('simple', $1)) DESC LIMIT $3
        ''',
        question,
        workspace_id,
        limit,
    )
    merged: dict[str, dict] = {}
    for rank, row in enumerate(dense, 1):
        item = dict(row)
        item['_dense_rank'] = rank
        item['_rank'] = rank
        merged[str(row['id'])] = item
    for rank, row in enumerate(keyword, 1):
        key = str(row['id'])
        item = merged.setdefault(key, dict(row) | {'_dense_rank': 999, '_rank': 999})
        item['_keyword_rank'] = rank
        item['_rrf'] = 1 / (60 + item.get('_dense_rank', 999)) + 1 / (60 + rank)
    results = sorted(merged.values(), key=lambda item: item.get('_rrf', 0), reverse=True)[:limit]
    for index, item in enumerate(results, 1):
        item['_rank'] = index
    try:
        results = await rerank(question, results[:8])
    except Exception:
        # The evidence is still grounded in the real database ranking if optional reranking fails.
        pass
    return results


async def conflicts_for_documents(workspace_id: str, document_ids: list[str]) -> list[dict]:
    if not document_ids:
        return []
    rows = await db.fetch(
        '''
        SELECT c.id, c.subject, c.field_type, c.severity, c.nli_label, c.reason,
               cl.id AS claim_id, cl.document_id, cl.filename, cl.page_number,
               cl.section_heading, cl.quote, cl.claim_value, cl.document_date_hint,
               cl.version_hint
        FROM conflicts c JOIN conflict_claims cl ON cl.conflict_id = c.id
        WHERE c.workspace_id = $1 AND c.nli_label = 'contradiction'
          AND cl.document_id = ANY($2::uuid[])
        ORDER BY CASE c.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                 c.created_at DESC
        ''',
        workspace_id,
        document_ids,
    )
    grouped: dict[str, dict] = {}
    for row in rows:
        key = str(row['id'])
        grouped.setdefault(
            key,
            {
                'id': key,
                'subject': row['subject'],
                'field_type': row['field_type'],
                'severity': row['severity'],
                'reason': row['reason'],
                'claims': [],
            },
        )['claims'].append(dict(row))
    return list(grouped.values())

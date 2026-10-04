from __future__ import annotations

from .db import db
from .providers import rerank


async def retrieve(
    workspace_id: str,
    question: str,
    limit: int = 12,
) -> list[dict]:
    """
    Retrieve evidence using PostgreSQL full-text search only.

    No embeddings are generated here, so this works without
    OpenAI API credits or SentenceTransformer model loading.
    """

    keyword = await db.fetch(
        '''
        SELECT
            c.id,
            c.document_id,
            c.page_id,
            c.text_content,
            c.page_number,
            c.section_heading,
            c.ocr_confidence,
            d.filename,
            d.document_date_hint,
            d.version_hint,
            d.section_citation_only,
            ts_rank_cd(
                c.search_vector,
                plainto_tsquery('simple', $1)
            ) AS score
        FROM chunks c
        JOIN documents d
            ON d.id = c.document_id
        WHERE c.workspace_id = $2
        ORDER BY ts_rank_cd(
            c.search_vector,
            plainto_tsquery('simple', $1)
        ) DESC
        LIMIT $3
        ''',
        question,
        workspace_id,
        limit,
    )

    results = [dict(row) for row in keyword]

    for index, item in enumerate(results, 1):
        item['_rank'] = index
        item['_keyword_rank'] = index

    # Optional reranking.
    # If the configured reranker is unavailable, keep the
    # PostgreSQL search results instead of failing the query.
    try:
        results = await rerank(
            question,
            results[:8],
        )
    except Exception:
        pass

    return results


async def conflicts_for_documents(
    workspace_id: str,
    document_ids: list[str],
) -> list[dict]:
    """
    Return detected contradictions for the selected documents.
    """

    if not document_ids:
        return []

    rows = await db.fetch(
        '''
        SELECT
            c.id,
            c.subject,
            c.field_type,
            c.severity,
            c.nli_label,
            c.reason,
            cl.id AS claim_id,
            cl.document_id,
            cl.filename,
            cl.page_number,
            cl.section_heading,
            cl.quote,
            cl.claim_value,
            cl.document_date_hint,
            cl.version_hint
        FROM conflicts c
        JOIN conflict_claims cl
            ON cl.conflict_id = c.id
        WHERE c.workspace_id = $1
          AND c.nli_label = 'contradiction'
          AND cl.document_id = ANY($2::uuid[])
        ORDER BY
            CASE c.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                ELSE 3
            END,
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

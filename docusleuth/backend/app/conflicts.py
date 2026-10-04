from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from .db import db
from .providers import compare_claims
from .settings import get_settings


def _quote(text: str | None, fallback: str) -> str:
    value = (text or fallback).strip()
    return value[:1200]


async def candidate_pairs(workspace_id: str, document_id: str | None = None, limit: int = 201) -> list[dict]:
    extra = ''
    args: list[object] = [workspace_id]
    if document_id:
        extra = ' AND (a.document_id = $2 OR b.document_id = $2)'
        args.append(document_id)
    args.append(limit)
    rows = await db.fetch(
        f'''
        SELECT a.id AS a_entity_id, b.id AS b_entity_id,
               a.document_id AS a_document_id, b.document_id AS b_document_id,
               a.chunk_id AS a_chunk_id, b.chunk_id AS b_chunk_id,
               a.page_number AS a_page_number, b.page_number AS b_page_number,
               a.entity_type, a.subject, a.normalized_subject,
               a.raw_value AS a_raw_value, b.raw_value AS b_raw_value,
               a.normalized_value AS a_normalized_value,
               b.normalized_value AS b_normalized_value,
               a.document_date_hint AS a_date_hint, b.document_date_hint AS b_date_hint,
               a.version_hint AS a_version_hint, b.version_hint AS b_version_hint,
               da.filename AS a_filename, dbb.filename AS b_filename,
               ca.text_content AS a_text, cb.text_content AS b_text,
               ca.section_heading AS a_section, cb.section_heading AS b_section
        FROM document_entities a
        JOIN document_entities b
          ON a.workspace_id = b.workspace_id
         AND a.entity_type = b.entity_type
         AND a.normalized_subject = b.normalized_subject
         AND a.normalized_value <> b.normalized_value
         AND a.document_id < b.document_id
        JOIN documents da ON da.id = a.document_id
        JOIN documents dbb ON dbb.id = b.document_id
        LEFT JOIN chunks ca ON ca.id = a.chunk_id
        LEFT JOIN chunks cb ON cb.id = b.chunk_id
        WHERE a.workspace_id = $1 {extra}
        ORDER BY a.created_at, b.created_at
        LIMIT ${len(args)}
        ''',
        *args,
    )
    return [dict(row) for row in rows]


async def _analyze_one(workspace_id: str, scan_id: str | None, row: dict) -> bool:
    claim_a = f"{row['a_subject'] if 'a_subject' in row else row['subject']}: {row['a_raw_value']}\nSource: {row['a_text'] or row['a_raw_value']}"
    claim_b = f"{row['subject']}: {row['b_raw_value']}\nSource: {row['b_text'] or row['b_raw_value']}"
    result = await compare_claims(row['subject'], row['entity_type'], claim_a, claim_b)
    if result['label'] != 'contradiction' or not result['subject_match']:
        return False
    conflict_key = f"{row['a_entity_id']}:{row['b_entity_id']}"
    conflict = await db.fetchrow(
        '''
        INSERT INTO conflicts (workspace_id, scan_id, conflict_key, subject, field_type,
                               severity, nli_label, subject_match, reason)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (workspace_id, conflict_key) DO UPDATE SET
          severity = EXCLUDED.severity, nli_label = EXCLUDED.nli_label,
          subject_match = EXCLUDED.subject_match, reason = EXCLUDED.reason
        RETURNING id
        ''',
        workspace_id,
        scan_id,
        conflict_key,
        row['subject'],
        row['entity_type'],
        result['severity'],
        result['label'],
        result['subject_match'],
        result['reason'],
    )
    if conflict:
        conflict_id = conflict['id']
        await db.execute('DELETE FROM conflict_claims WHERE conflict_id = $1', conflict_id)
        await db.execute(
            '''
            INSERT INTO conflict_claims (conflict_id, document_id, chunk_id, filename, page_number,
                                         section_heading, quote, claim_value, document_date_hint, version_hint)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10),
                   ($1,$11,$12,$13,$14,$15,$16,$17,$18,$19)
            ''',
            conflict_id,
            row['a_document_id'], row['a_chunk_id'], row['a_filename'], row['a_page_number'],
            row['a_section'], _quote(row['a_text'], row['a_raw_value']), row['a_raw_value'],
            row['a_date_hint'], row['a_version_hint'],
            row['b_document_id'], row['b_chunk_id'], row['b_filename'], row['b_page_number'],
            row['b_section'], _quote(row['b_text'], row['b_raw_value']), row['b_raw_value'],
            row['b_date_hint'], row['b_version_hint'],
        )
    return True


async def analyze_rows(workspace_id: str, rows: Iterable[dict], scan_id: str | None = None) -> int:
    semaphore = asyncio.Semaphore(4)

    async def guarded(row: dict) -> bool:
        async with semaphore:
            try:
                return await _analyze_one(workspace_id, scan_id, row)
            except Exception:
                return False

    results = await asyncio.gather(*(guarded(row) for row in rows))
    return sum(1 for result in results if result)


async def detect_for_document(workspace_id: str, document_id: str) -> int:
    rows = await candidate_pairs(workspace_id, document_id, get_settings().max_conflict_candidates + 1)
    return await analyze_rows(workspace_id, rows[: get_settings().max_conflict_candidates])


async def run_scan(scan_id: str, workspace_id: str) -> None:
    try:
        await db.execute("UPDATE conflict_scans SET status = 'running' WHERE id = $1", scan_id)
        cap = get_settings().max_conflict_candidates
        rows = await candidate_pairs(workspace_id, None, cap + 1)
        cap_hit = len(rows) > cap
        rows = rows[:cap]
        await db.execute(
            'UPDATE conflict_scans SET candidate_count = $2, cap_hit = $3 WHERE id = $1',
            scan_id,
            len(rows),
            cap_hit,
        )
        await analyze_rows(workspace_id, rows, scan_id)
        await db.execute(
            "UPDATE conflict_scans SET status = 'ready', completed_at = now() WHERE id = $1",
            scan_id,
        )
    except Exception as exc:
        await db.execute(
            "UPDATE conflict_scans SET status = 'failed', error_message = $2, completed_at = now() WHERE id = $1",
            scan_id,
            str(exc)[:1000],
        )


def schedule_scan(scan_id: str, workspace_id: str) -> None:
    asyncio.create_task(run_scan(scan_id, workspace_id))


async def list_conflicts(workspace_id: str) -> list[dict]:
    rows = await db.fetch(
        '''
        SELECT c.id, c.subject, c.field_type, c.severity, c.nli_label, c.subject_match,
               c.reason, c.created_at, cl.id AS claim_id, cl.document_id, cl.filename,
               cl.page_number, cl.section_heading, cl.quote, cl.claim_value,
               cl.document_date_hint, cl.version_hint
        FROM conflicts c JOIN conflict_claims cl ON cl.conflict_id = c.id
        WHERE c.workspace_id = $1 AND c.nli_label = 'contradiction'
        ORDER BY CASE c.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                 c.created_at DESC
        ''',
        workspace_id,
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

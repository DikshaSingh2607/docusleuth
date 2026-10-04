from __future__ import annotations

import asyncio
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import fitz
import pytesseract
from PIL import Image, ImageFilter, ImageOps
from docx import Document as DocxDocument

from .conflicts import detect_for_document
from .db import db
from .providers import embed_texts, extract_entities
from .settings import get_settings
from .workflow import generate_document_summary


@dataclass
class PageContent:
    page_number: int | None
    section_heading: str | None
    text: str
    ocr_confidence: float | None = None
    ocr_boxes: list[dict[str, Any]] | None = None


def validate_signature(filename: str, mime_type: str, content: bytes) -> None:
    if not content:
        raise ValueError(f'File is empty: {filename}.')
    lower = filename.lower()
    valid = (
        (lower.endswith('.pdf') and content.startswith(b'%PDF-'))
        or (lower.endswith(('.png',)) and content.startswith(b'\x89PNG\r\n\x1a\n'))
        or (lower.endswith(('.jpg', '.jpeg')) and content.startswith(b'\xff\xd8\xff'))
        or (lower.endswith('.docx') and content.startswith(b'PK'))
        or (lower.endswith('.txt') and b'\x00' not in content[:4096])
    )
    if not valid:
        raise ValueError(f'File signature does not match a supported document type for {filename}.')


def _ocr_image(image: Image.Image) -> tuple[str, float, list[dict[str, Any]]]:
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    data = pytesseract.image_to_data(image, lang=get_settings().ocr_languages, output_type=pytesseract.Output.DICT)
    parts: list[str] = []
    confidences: list[float] = []
    boxes: list[dict[str, Any]] = []
    for index, value in enumerate(data.get('text', [])):
        value = value.strip()
        try:
            confidence = float(data['conf'][index])
        except (ValueError, TypeError, KeyError):
            confidence = -1
        if value and confidence >= 0:
            parts.append(value)
            confidences.append(confidence)
            boxes.append({
                'text': value,
                'left': data['left'][index], 'top': data['top'][index],
                'width': data['width'][index], 'height': data['height'][index],
                'confidence': confidence,
            })
    return ' '.join(parts), (sum(confidences) / len(confidences) / 100 if confidences else 0), boxes


def _heading(text: str) -> str | None:
    first = next((line.strip() for line in text.splitlines() if line.strip()), '')
    if 2 <= len(first) <= 120 and (first.isupper() or re.match(r'^(section|article|chapter|part)\b', first, re.I)):
        return first
    return None


def extract_bytes(filename: str, mime_type: str, content: bytes) -> tuple[list[PageContent], bool]:
    validate_signature(filename, mime_type, content)
    lower = filename.lower()
    if lower.endswith('.pdf'):
        pages: list[PageContent] = []
        scanned = False
        with fitz.open(stream=content, filetype='pdf') as pdf:
            if pdf.needs_pass:
                raise ValueError('This PDF is password-protected and cannot be indexed.')
            for number in range(pdf.page_count):
                page = pdf.load_page(number)
                page_number = number + 1
                text = page.get_text('text').strip()
                if len(re.sub(r'\s+', '', text)) < 30:
                    scanned = True
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes('png')))
                    text, confidence, boxes = _ocr_image(image)
                    pages.append(PageContent(page_number, _heading(text), text, confidence, boxes))
                else:
                    pages.append(PageContent(page_number, _heading(text), text, None, None))
        return pages, scanned
    if lower.endswith(('.png', '.jpg', '.jpeg')):
        image = Image.open(io.BytesIO(content))
        text, confidence, boxes = _ocr_image(image)
        return [PageContent(1, _heading(text), text, confidence, boxes)], True
    if lower.endswith('.txt'):
        text = content.decode('utf-8', errors='replace').strip()
        return [PageContent(1, _heading(text), text, None, None)], False
    if lower.endswith('.docx'):
        document = DocxDocument(io.BytesIO(content))
        sections: list[str] = []
        for paragraph in document.paragraphs:
            value = paragraph.text.strip()
            if value:
                sections.append(value)
        for table in document.tables:
            for row in table.rows:
                sections.append(' | '.join(cell.text.strip() for cell in row.cells))
        text = '\n'.join(sections).strip()
        return [PageContent(None, _heading(text), text, None, None)], False
    raise ValueError('Unsupported document type.')


def chunk_page(page: PageContent, target_words: int = 430, overlap_words: int = 60) -> list[dict]:
    words = list(re.finditer(r'\S+', page.text))
    if not words:
        return []
    chunks: list[dict] = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        start_offset = words[start].start()
        end_offset = words[end - 1].end()
        chunks.append({
            'text': page.text[start_offset:end_offset],
            'page_number': page.page_number,
            'section_heading': page.section_heading,
            'start_offset': start_offset,
            'end_offset': end_offset,
            'ocr_confidence': page.ocr_confidence,
        })
        if end == len(words):
            break
        start = max(end - overlap_words, start + 1)
    return chunks


async def _claim_job() -> dict | None:
    async with db.transaction() as conn:
        row = await conn.fetchrow(
            '''
            SELECT id, document_id, workspace_id
            FROM ingestion_jobs
            WHERE status IN ('queued','failed')
              AND attempts < 4
              AND (lease_until IS NULL OR lease_until < now())
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED LIMIT 1
            '''
        )
        if not row:
            return None
        await conn.execute(
            '''
            UPDATE ingestion_jobs
            SET status = 'extracting', attempts = attempts + 1,
                lease_until = $2, updated_at = now(), error_message = NULL
            WHERE id = $1
            ''',
            row['id'], datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        await conn.execute(
            "UPDATE documents SET status = 'extracting', updated_at = now(), error_message = NULL WHERE id = $1",
            row['document_id'],
        )
        return dict(row)


async def _status(job_id, document_id, status: str, error: str | None = None) -> None:
    await db.execute(
        'UPDATE ingestion_jobs SET status = $2, error_message = $3, updated_at = now(), lease_until = NULL WHERE id = $1',
        job_id, status, error,
    )
    await db.execute(
        'UPDATE documents SET status = $2, error_message = $3, updated_at = now() WHERE id = $1',
        document_id, status, error,
    )


async def process_job(job: dict) -> None:
    document = await db.fetchrow(
        'SELECT * FROM documents WHERE id = $1 AND workspace_id = $2', job['document_id'], job['workspace_id']
    )
    if not document:
        raise ValueError('Document record disappeared before ingestion.')
    try:
        pages, scanned = await asyncio.to_thread(
            extract_bytes, document['safe_filename'], document['mime_type'], bytes(document['content'])
        )
        if not any(page.text.strip() for page in pages):
            raise ValueError('No extractable text found after OCR.')
        if document['safe_filename'].lower().endswith('.docx'):
            await db.execute(
                'UPDATE documents SET section_citation_only = true, updated_at = now() WHERE id = $1',
                job['document_id'],
            )
        await _status(job['id'], job['document_id'], 'OCR' if scanned else 'extracting')
        all_chunks: list[dict] = []
        async with db.transaction() as conn:
            await conn.execute('DELETE FROM document_pages WHERE document_id = $1', job['document_id'])
            await conn.execute('DELETE FROM chunks WHERE document_id = $1', job['document_id'])
            await conn.execute('DELETE FROM document_entities WHERE document_id = $1', job['document_id'])
            for page in pages:
                page_row = await conn.fetchrow(
                    '''
                    INSERT INTO document_pages (document_id, workspace_id, page_number, section_heading,
                                                text_content, ocr_confidence, ocr_boxes)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id
                    ''',
                    job['document_id'], job['workspace_id'], page.page_number, page.section_heading,
                    page.text, page.ocr_confidence,
                    json.dumps(page.ocr_boxes) if page.ocr_boxes else None,
                )
                for chunk in chunk_page(page):
                    chunk['page_id'] = page_row['id']
                    all_chunks.append(chunk)
        await _status(job['id'], job['document_id'], 'indexing')

        # Free deployment fallback:
        # Store chunks without embeddings and rely on PostgreSQL full-text search.
        vectors = [None for _ in all_chunks]

        entity_source = '\n\n'.join(page.text for page in pages)
        entities = await extract_entities(entity_source) if entity_source else []
        await generate_document_summary(str(job['workspace_id']), str(job['document_id']), entity_source)
        async with db.transaction() as conn:
            chunk_ids: list[Any] = []
            for chunk, vector in zip(all_chunks, vectors):
                row = await conn.fetchrow(
                    '''
                    INSERT INTO chunks (document_id, page_id, workspace_id, text_content, page_number,
                                        section_heading, start_offset, end_offset, ocr_confidence, embedding)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::vector) RETURNING id
                    ''',
                    job['document_id'], chunk['page_id'], job['workspace_id'], chunk['text'],
                    chunk['page_number'], chunk['section_heading'], chunk['start_offset'],
                    chunk['end_offset'], chunk['ocr_confidence'], '[' + ','.join(str(x) for x in vector) + ']',
                )
                chunk_ids.append(row['id'])
            for entity in entities:
                raw = str(entity.get('raw_value', '')).strip()
                if not raw:
                    continue
                match = next((i for i, chunk in enumerate(all_chunks) if raw.lower() in chunk['text'].lower()), None)
                chunk_id = chunk_ids[match] if match is not None else None
                page_number = all_chunks[match]['page_number'] if match is not None else None
                subject = str(entity.get('subject', '')).strip()
                normalized_subject = re.sub(r'\s+', ' ', subject.casefold())
                normalized_value = re.sub(r'\s+', ' ', str(entity.get('normalized_value', raw)).casefold()).strip()
                if subject and normalized_value:
                    await conn.execute(
                        '''
                        INSERT INTO document_entities (workspace_id, document_id, chunk_id, page_number,
                                                       entity_type, subject, normalized_subject, raw_value,
                                                       normalized_value, confidence)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        ''',
                        job['workspace_id'], job['document_id'], chunk_id, page_number,
                        entity.get('entity_type', 'status'), subject, normalized_subject, raw,
                        normalized_value, float(entity.get('confidence', 0.5)),
                    )
            await conn.execute(
                "UPDATE documents SET status = 'ready', updated_at = now() WHERE id = $1",
                job['document_id'],
            )
            await conn.execute(
                "UPDATE ingestion_jobs SET status = 'ready', updated_at = now(), lease_until = NULL WHERE id = $1",
                job['id'],
            )
        await detect_for_document(str(job['workspace_id']), str(job['document_id']))
    except Exception as exc:
        await _status(job['id'], job['document_id'], 'failed', str(exc)[:1200])


class IngestionWorker:
    def __init__(self) -> None:
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task | None = None

    async def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                job = await _claim_job()
                if job:
                    await process_job(job)
                else:
                    await asyncio.sleep(1.5)
            except Exception:
                await asyncio.sleep(3)

    def start(self) -> None:
        self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            await self.task

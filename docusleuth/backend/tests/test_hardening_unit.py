from pathlib import Path

import fitz
import pytest
from PIL import Image

from backend.app.api import _citations
from backend.app.ingestion import PageContent, chunk_page, extract_bytes


def test_chunking_has_offsets_and_overlap() -> None:
    text = ' '.join(f'word{i}' for i in range(900))
    chunks = chunk_page(PageContent(2, 'SECTION A', text), target_words=100, overlap_words=20)
    assert len(chunks) > 1
    assert all(chunk['start_offset'] < chunk['end_offset'] for chunk in chunks)
    assert chunks[0]['page_number'] == 2
    assert chunks[1]['start_offset'] < chunks[0]['end_offset']


def test_citation_mapping_preserves_stored_chunk_fields() -> None:
    citations = _citations([{
        'id': 'chunk-1', 'document_id': 'doc-1', 'filename': 'source.pdf',
        'page_number': 4, 'section_heading': 'Terms', 'text_content': 'Exact stored quote',
        'ocr_confidence': 0.91, 'document_date_hint': '2026-01-01', 'version_hint': 'v2',
        'section_citation_only': False,
    }])
    assert citations == [{
        'number': 1, 'chunk_id': 'chunk-1', 'document_id': 'doc-1', 'filename': 'source.pdf',
        'page': 4, 'section': 'Terms', 'quote': 'Exact stored quote', 'ocr_confidence': 0.91,
        'date_hint': '2026-01-01', 'version_hint': 'v2', 'section_citation_only': False,
    }]


def test_tenant_bound_queries_include_workspace_predicates() -> None:
    api = Path(__file__).parents[1] / 'app' / 'api.py'
    source = api.read_text(encoding='utf-8')
    assert 'WHERE document_id = $1 AND workspace_id = $2' in source
    assert 'WHERE id = $1 AND workspace_id = $2' in source
    assert 'WHERE c.id = $1 AND c.workspace_id = $2' in (Path(__file__).parents[1] / 'app' / 'workflow.py').read_text(encoding='utf-8')


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ValueError, match='empty'):
        extract_bytes('empty.txt', 'text/plain', b'')


def test_corrupt_pdf_is_rejected() -> None:
    with pytest.raises(Exception):
        extract_bytes('corrupt.pdf', 'application/pdf', b'%PDF-not-a-real-file')


def test_password_protected_pdf_is_rejected() -> None:
    source = fitz.open()
    source.new_page().insert_text((72, 72), 'protected text')
    protected = source.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='user')
    with pytest.raises(ValueError, match='password-protected'):
        extract_bytes('protected.pdf', 'application/pdf', protected)


def test_image_with_no_text_is_extractable_but_empty() -> None:
    image = Image.new('RGB', (800, 600), 'white')
    import io
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    pages, _ = extract_bytes('blank.png', 'image/png', buffer.getvalue())
    assert pages and pages[0].text == ''


def test_mixed_language_text_preserves_unicode() -> None:
    text = 'English clause — 契約条項 — cláusula española'
    pages, _ = extract_bytes('mixed.txt', 'text/plain', text.encode('utf-8'))
    assert pages[0].text == text

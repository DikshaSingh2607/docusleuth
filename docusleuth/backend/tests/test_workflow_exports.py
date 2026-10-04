from backend.app.workflow import export_markdown, export_pdf


def test_empty_investigation_exports_without_sample_data() -> None:
    model = {
        'generated_at': 'test',
        'documents': [],
        'history': [],
        'conflicts': [],
        'trust_decisions': [],
        'pins': [],
    }
    markdown = export_markdown(model)
    pdf = export_pdf(markdown)
    assert '# DocuSleuth Investigation' in markdown
    assert pdf.startswith(b'%PDF')

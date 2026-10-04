import os
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.mark.integration
def test_real_upload_to_answer_flow() -> None:
    required = ['DATABASE_URL', 'OPENAI_EMBEDDINGS_API_KEY', 'LLM_API_KEY', 'APP_SESSION_SECRET']
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip('BLOCKED: missing protected real-service configuration: ' + ', '.join(missing))
    with TestClient(app) as client:
        health = client.get('/health').json()
        if not health.get('database_ready'):
            pytest.skip('BLOCKED: external PostgreSQL is not connected')
        response = client.post('/api/upload', files={'files': ('answer.txt', b'Amount due is 42 dollars.', 'text/plain')})
        assert response.status_code == 200, response.text
        document_id = response.json()['documents'][0]['id']
        for _ in range(60):
            jobs = client.get('/api/jobs').json()
            job = next(item for item in jobs if item['document_id'] == document_id)
            if job['status'] == 'ready':
                break
            if job['status'] == 'failed':
                pytest.fail(job.get('error_message') or 'ingestion failed')
        else:
            pytest.fail('ingestion did not become ready within the integration timeout')
        answer = client.post('/api/chat/stream', json={'question': 'What amount is due?'})
        assert answer.status_code == 200, answer.text
        done_line = next(line[6:] for line in answer.text.splitlines() if line.startswith('data: {') and '"answer"' in line)
        done = json.loads(done_line)
        assert done['answer'] == 'I could not find this in the uploaded documents.' or '[1]' in done['answer']

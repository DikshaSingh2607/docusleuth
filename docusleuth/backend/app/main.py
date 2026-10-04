from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .db import db
from .ingestion import IngestionWorker
from .settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('docusleuth')
worker = IngestionWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await db.connect()
        if db.pool:
            worker.start()
    except Exception:
        logger.error('Database startup failed; protected routes will report the setup error without exposing connection details.')
    yield
    await worker.stop()
    await db.close()


app = FastAPI(title='DocuSleuth API', version='0.1.0', lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization'],
    expose_headers=['Content-Disposition'],
)


@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Content-Security-Policy'] = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-src 'self' blob:; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' http://localhost:8000 https://api.openai.com; frame-ancestors https://*.manus.computer http://localhost:3000"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    return response
app.include_router(router)


@app.get('/health')
async def health() -> dict[str, str | bool]:
    return {'status': 'ok', 'service': 'docusleuth-api', 'database_ready': bool(db.pool)}


@app.get('/api/health')
async def api_health() -> dict[str, str | bool]:
    return await health()


@app.get('/', include_in_schema=False)
async def root():
    index = Path(__file__).resolve().parents[2] / 'frontend' / 'out' / 'index.html'
    if index.exists():
        return FileResponse(index)
    return {'service': 'DocuSleuth API', 'health': '/health'}


static_root = Path(__file__).resolve().parents[2] / 'frontend' / 'out'
if static_root.exists():
    app.mount('/', StaticFiles(directory=static_root, html=True), name='frontend')

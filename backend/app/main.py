"""FastAPI application entrypoint — Phase P0.

- Bootstraps the local SQLite DB (data/sih_local.db) on startup.
- Mounts the v1 routers (upload, validation, dashboard, jobs).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import db
from app.core.config import settings
from app.api.routes import dashboard, jobs, upload, validation


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()  # idempotent: CREATE IF NOT EXISTS + seed demo rule
    yield


app = FastAPI(title="GeM Bid Compliance Verification API",
              version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (upload.router, validation.router, dashboard.router, jobs.router):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["meta"])
def health():
    from app import __version__
    return {"status": "ok", "service": "ge_m-compliance-backend", "version": __version__}
"""FastAPI application entrypoint.

Stub — mounts routers, health endpoint, CORS. Implement per docs/01.
The router implementations live in app/api/routes/ and delegate to
app/services/orchestrator.py for pipeline execution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import dashboard, jobs, upload, validation

app = FastAPI(title="GeM Bid Compliance Verification API", version="0.1.0")

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
    return {"status": "ok", "service": "ge_m-compliance-backend", "version": __import__("app").__version__}
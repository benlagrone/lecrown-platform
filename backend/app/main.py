from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import desc, select

from app.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.security import authenticate_access_token
from app.models.gov_contract import GovContractImportRun
from app.routes import auth, backoffice, billing, client_portal, content, distribution, documents, gov_contract, intake, inquiry, invoice, linkedin, youtube
from app.services import gov_contract_service
from app.services import espocrm_service

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_BACKOFFICE_PATHS = {
    "/healthz",
    "/auth/config",
    "/auth/google",
    "/auth/login",
    "/auth/accept-invite",
}
CLIENT_PORTAL_PATHS = {
    "/healthz",
    "/client-portal/config",
    "/client-portal/session",
}


@app.middleware("http")
async def require_backoffice_workspace_identity(request: Request, call_next):
    host = request.headers.get("host", "").partition(":")[0].strip().casefold()
    if host == settings.client_portal_host and request.url.path not in CLIENT_PORTAL_PATHS:
        return JSONResponse(status_code=404, content={"detail": "Route not found"})
    if (
        settings.workspace_auth_required
        and host == settings.workspace_auth_host
        and request.method != "OPTIONS"
        and request.url.path not in PUBLIC_BACKOFFICE_PATHS
    ):
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token.strip():
            return JSONResponse(status_code=401, content={"detail": "Google Workspace sign-in required"})
        try:
            with SessionLocal() as db:
                authenticate_access_token(db, token.strip())
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/healthz")
def healthcheck() -> dict[str, object]:
    gmail_latest_run: dict[str, object] | None = None
    with SessionLocal() as db:
        latest_gmail_run = db.scalars(
            select(GovContractImportRun)
            .where(GovContractImportRun.source == gov_contract_service.GMAIL_RFQ_SOURCE_NAME)
            .order_by(desc(GovContractImportRun.completed_at), desc(GovContractImportRun.created_at))
            .limit(1)
        ).first()
        if latest_gmail_run is not None:
            gmail_latest_run = {
                "status": latest_gmail_run.status,
                "total_records": latest_gmail_run.total_records,
                "matched_records": latest_gmail_run.matched_records,
                "open_records": latest_gmail_run.open_records,
                "source_total_records": latest_gmail_run.source_total_records,
                "completed_at": latest_gmail_run.completed_at.isoformat() if latest_gmail_run.completed_at else None,
                "error_message": latest_gmail_run.error_message,
            }

    return {
        "status": "ok",
        "checks": {
            "espocrm_base_url": espocrm_service.has_base_url(),
            "espocrm_credentials": espocrm_service.has_credentials(),
            "espocrm_configured": espocrm_service.is_configured(),
            "gmail_rfq_feed_url": bool(settings.gmail_rfq_feed_url.strip()),
            "gmail_rfq_direct": settings.gmail_rfq_direct_enabled,
            "gmail_rfq_configured": settings.gmail_rfq_feed_enabled,
            "gmail_rfq_latest_run": gmail_latest_run,
        },
    }


app.include_router(content.router, prefix="/content", tags=["content"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(invoice.router, prefix="/invoice", tags=["invoice"])
app.include_router(gov_contract.router, prefix="/contracts", tags=["contracts"])
app.include_router(intake.router, prefix="/intake", tags=["intake"])
app.include_router(inquiry.router, prefix="/inquiry", tags=["inquiry"])
app.include_router(linkedin.router, prefix="/linkedin", tags=["linkedin"])
app.include_router(youtube.router, prefix="/youtube", tags=["youtube"])
app.include_router(distribution.router, prefix="/distribution", tags=["distribution"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(backoffice.router, prefix="/backoffice", tags=["backoffice"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(client_portal.router, prefix="/client-portal", tags=["client-portal"])

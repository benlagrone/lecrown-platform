from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.database import init_db
from app.routes import auth, content, distribution, inquiry, linkedin, youtube

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(content.router, prefix="/content", tags=["content"])
app.include_router(inquiry.router, prefix="/inquiry", tags=["inquiry"])
app.include_router(linkedin.router, prefix="/linkedin", tags=["linkedin"])
app.include_router(youtube.router, prefix="/youtube", tags=["youtube"])
app.include_router(distribution.router, prefix="/distribution", tags=["distribution"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])

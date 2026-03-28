import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = os.getenv("APP_NAME", "LeCrown Platform")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./lecrown.db")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    linkedin_token: str = os.getenv("LINKEDIN_TOKEN", "")
    linkedin_org_id_dev: str = os.getenv("LINKEDIN_ORG_ID_DEV", "")
    linkedin_org_id_prop: str = os.getenv("LINKEDIN_ORG_ID_PROP", "")

    youtube_access_token_dev: str = os.getenv("YOUTUBE_ACCESS_TOKEN_DEV", "")
    youtube_access_token_prop: str = os.getenv("YOUTUBE_ACCESS_TOKEN_PROP", "")
    youtube_refresh_token_dev: str = os.getenv("YOUTUBE_REFRESH_TOKEN_DEV", "")
    youtube_refresh_token_prop: str = os.getenv("YOUTUBE_REFRESH_TOKEN_PROP", "")
    youtube_client_id: str = os.getenv("YOUTUBE_CLIENT_ID", "")
    youtube_client_secret: str = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    youtube_category_id: str = os.getenv("YOUTUBE_CATEGORY_ID", "22")
    youtube_privacy_status: str = os.getenv("YOUTUBE_PRIVACY_STATUS", "private")

    video_render_mode: str = os.getenv("VIDEO_RENDER_MODE", "stub")
    video_server_url: str = os.getenv("VIDEO_SERVER_URL", "http://127.0.0.1:8001")
    video_render_endpoint: str = os.getenv("VIDEO_RENDER_ENDPOINT", "/render")
    video_render_timeout_seconds: int = int(os.getenv("VIDEO_RENDER_TIMEOUT_SECONDS", "600"))
    video_render_default_style: str = os.getenv("VIDEO_RENDER_DEFAULT_STYLE", "default")
    video_stub_video_path: str = os.getenv("VIDEO_STUB_VIDEO_PATH", "")
    video_stub_video_url: str = os.getenv("VIDEO_STUB_VIDEO_URL", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")

    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()

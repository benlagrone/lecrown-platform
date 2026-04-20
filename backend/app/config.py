import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = os.getenv("APP_NAME", "LeCrown Platform")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./lecrown.db")
    public_app_url: str = os.getenv("PUBLIC_APP_URL", "")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_publishable_key: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe_api_version: str = os.getenv("STRIPE_API_VERSION", "2026-02-25.clover")
    stripe_portal_configuration_id: str = os.getenv("STRIPE_PORTAL_CONFIGURATION_ID", "")
    billing_service_keys: str = os.getenv("BILLING_SERVICE_KEYS", "")
    google_oauth_client_id: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    google_oauth_client_secret: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    gmail_refresh_token_benjaminlagrone_gmail_com: str = os.getenv(
        "GMAIL_REFRESH_TOKEN_BENJAMINLAGRONE_GMAIL_COM",
        "",
    )
    gmail_refresh_token_benjamin_lecrownproperties_com: str = os.getenv(
        "GMAIL_REFRESH_TOKEN_BENJAMIN_LECROWNPROPERTIES_COM",
        "",
    )
    invoice_output_dir: str = os.getenv("INVOICE_OUTPUT_DIR", "./invoice-output")

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
    admin_email: str = os.getenv("ADMIN_EMAIL", "")
    invite_sender_email: str = os.getenv("INVITE_SENDER_EMAIL", "")
    user_invite_expire_days: int = int(os.getenv("USER_INVITE_EXPIRE_DAYS", "7"))
    intake_api_key: str = os.getenv("INTAKE_API_KEY", "")

    espocrm_base_url: str = os.getenv("ESPOCRM_BASE_URL", "")
    espocrm_api_key: str = os.getenv("ESPOCRM_API_KEY", "")
    espocrm_username: str = os.getenv("ESPOCRM_USERNAME", "")
    espocrm_password: str = os.getenv("ESPOCRM_PASSWORD", "")
    espocrm_timeout_seconds: int = int(os.getenv("ESPOCRM_TIMEOUT_SECONDS", "15"))

    gov_contract_service_url: str = os.getenv(
        "GOV_CONTRACT_SERVICE_URL",
        "https://www.txsmartbuy.gov/app/extensions/CPA/CPAMain/1.0.0/services/ESBD.Service.ss",
    )
    gov_contract_source_base_url: str = os.getenv(
        "GOV_CONTRACT_SOURCE_BASE_URL",
        "https://www.txsmartbuy.gov/esbd",
    )
    gov_contract_request_timeout_seconds: int = int(
        os.getenv("GOV_CONTRACT_REQUEST_TIMEOUT_SECONDS", "45")
    )
    federal_contract_service_url: str = os.getenv(
        "FEDERAL_CONTRACT_SERVICE_URL",
        "https://ag-dashboard.acquisitiongateway.gov/api/v3.0/resources/forecast",
    )
    federal_contract_source_base_url: str = os.getenv(
        "FEDERAL_CONTRACT_SOURCE_BASE_URL",
        "https://acquisitiongateway.gov/forecast",
    )
    federal_contract_request_timeout_seconds: int = int(
        os.getenv("FEDERAL_CONTRACT_REQUEST_TIMEOUT_SECONDS", "45")
    )
    federal_contract_page_size: int = int(os.getenv("FEDERAL_CONTRACT_PAGE_SIZE", "500"))
    grants_contract_export_url: str = os.getenv(
        "GRANTS_CONTRACT_EXPORT_URL",
        "https://simpler.grants.gov/api/search/export",
    )
    grants_contract_source_base_url: str = os.getenv(
        "GRANTS_CONTRACT_SOURCE_BASE_URL",
        "https://simpler.grants.gov/search",
    )
    grants_contract_request_timeout_seconds: int = int(
        os.getenv("GRANTS_CONTRACT_REQUEST_TIMEOUT_SECONDS", "60")
    )
    sba_subnet_source_url: str = os.getenv(
        "SBA_SUBNET_SOURCE_URL",
        "https://www.sba.gov/federal-contracting/contracting-guide/prime-subcontracting/subcontracting-opportunities",
    )
    sba_subnet_request_timeout_seconds: int = int(
        os.getenv("SBA_SUBNET_REQUEST_TIMEOUT_SECONDS", "45")
    )
    sba_subnet_max_pages: int = int(os.getenv("SBA_SUBNET_MAX_PAGES", "100"))
    gov_contract_window_days: int = int(os.getenv("GOV_CONTRACT_WINDOW_DAYS", "7"))
    gov_contract_match_min_score: int = int(os.getenv("GOV_CONTRACT_MATCH_MIN_SCORE", "4"))
    gov_contract_extra_keywords: list[str] = [
        keyword.strip()
        for keyword in os.getenv("GOV_CONTRACT_EXTRA_KEYWORDS", "").split(",")
        if keyword.strip()
    ]
    gmail_rfq_feed_url: str = os.getenv(
        "GMAIL_RFQ_FEED_URL",
        "",
    )
    gmail_rfq_feed_label: str = os.getenv("GMAIL_RFQ_FEED_LABEL", "RFQs/New")
    gmail_rfq_feed_timeout_seconds: int = int(os.getenv("GMAIL_RFQ_FEED_TIMEOUT_SECONDS", "20"))
    gmail_rfq_feed_limit: int = int(os.getenv("GMAIL_RFQ_FEED_LIMIT", "50"))
    gmail_rfq_match_score_floor: int = int(os.getenv("GMAIL_RFQ_MATCH_SCORE_FLOOR", "6"))

    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    @property
    def gmail_rfq_feed_enabled(self) -> bool:
        return bool(self.gmail_rfq_feed_url.strip())

    @property
    def billing_service_key_map(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for raw_pair in self.billing_service_keys.split(","):
            app_key, separator, secret = raw_pair.partition(":")
            cleaned_app_key = app_key.strip()
            cleaned_secret = secret.strip()
            if separator and cleaned_app_key and cleaned_secret:
                pairs[cleaned_app_key] = cleaned_secret
        return pairs

    @property
    def gmail_refresh_tokens(self) -> dict[str, str]:
        return {
            "benjaminlagrone@gmail.com": self.gmail_refresh_token_benjaminlagrone_gmail_com,
            "benjamin@lecrownproperties.com": self.gmail_refresh_token_benjamin_lecrownproperties_com,
        }

    @property
    def resolved_public_app_url(self) -> str:
        explicit = self.public_app_url.strip()
        if explicit:
            return explicit.rstrip("/")
        if self.cors_origins:
            return self.cors_origins[0].rstrip("/")
        return "http://localhost:3000"

    @property
    def invoice_output_path(self) -> Path:
        return Path(self.invoice_output_dir).expanduser()


@lru_cache
def get_settings() -> Settings:
    return Settings()

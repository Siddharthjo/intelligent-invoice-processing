from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

import json
import os


def _get_database_url() -> str:
    """
    On SAP BTP Cloud Foundry, database credentials are injected via VCAP_SERVICES.
    Fall back to DATABASE_URL env var for local development.
    """
    vcap = os.environ.get("VCAP_SERVICES")
    if vcap:
        services = json.loads(vcap)
        # HANA Cloud credentials
        for key in services:
            if "hana" in key.lower():
                creds = services[key][0]["credentials"]
                host = creds.get("host")
                port = creds.get("port", 443)
                user = creds.get("user")
                password = creds.get("password")
                if host and user and password:
                    # HANA Cloud only accepts TLS connections, and a `schema`-plan binding's
                    # tables live in `schema`, not in the technical user's default schema.
                    # URL.create escapes the (punctuation-heavy) generated password so it
                    # round-trips through make_url intact.
                    query = {"encrypt": "true", "sslValidateCertificate": "true"}
                    if creds.get("schema"):
                        query["currentSchema"] = creds["schema"]
                    return URL.create(
                        "hana+hdbcli",
                        username=user,
                        password=password,
                        host=host,
                        port=int(port),
                        query=query,
                    ).render_as_string(hide_password=False)
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://invoice_app:invoice_app@localhost:5432/invoice_processing"
    )

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = _get_database_url()

    max_upload_size_bytes: int = 20 * 1024 * 1024

    ocr_enabled: bool = True
    ocr_dpi: int = 300
    text_layer_min_chars_per_page: int = 20

    openai_api_key: str | None = None
    agent_model: str = "gpt-4o-mini"
    agent_max_tool_turns: int = 8
    agent_call_timeout_seconds: float = 30.0

    # Three-way match tolerance varies by PO type -- goods quantities are precise/countable
    # (tightest tolerance), services are often estimated (loosest), indirect in between.
    # Illustrative mock values, not derived from any real policy.
    agent_po_variance_tolerance_goods_pct: Decimal = Decimal("0.02")
    agent_po_variance_tolerance_services_pct: Decimal = Decimal("0.05")
    agent_po_variance_tolerance_indirect_pct: Decimal = Decimal("0.08")

    gmail_enabled: bool = False
    gmail_client_id: str | None = None
    gmail_client_secret: str | None = None
    gmail_refresh_token: str | None = None
    # Base search filter -- the label exclusions that make this idempotent are always
    # appended in code (see intake.gmail._effective_query), not baked in here, so they
    # can never drift out of sync with gmail_processed_label/gmail_failed_label below.
    #
    # Defaults to the last 7 days so a first run doesn't sweep the entire mailbox
    # history -- unscoped "has:attachment filename:pdf" matches every PDF attachment
    # you've ever received, not just invoices. For real use, scope this further:
    # e.g. "label:invoices has:attachment filename:pdf" against a dedicated Gmail
    # label/folder you (or a mail filter) route actual invoices into, rather than
    # relying on a date window against your whole inbox.
    gmail_query: str = "has:attachment filename:pdf newer_than:7d"
    gmail_processed_label: str = "invoice-processed"
    gmail_failed_label: str = "invoice-intake-failed"
    # None/0 disables the in-process scheduler; POST /gmail/check-now always works
    # regardless of this setting.
    gmail_poll_interval_minutes: int | None = None

    session_ttl_hours: int = 8
    # False for local http://localhost dev; set true for the Azure deployment (HTTPS).
    session_cookie_secure: bool = False

    # Illustrative gpt-4o-mini-ish pricing for the analytics cost *estimate* only --
    # not pulled from any real billing API, never presented as an actual invoiced
    # amount. Same "illustrative mock value" spirit as the PO variance tolerances above.
    agent_cost_per_1k_prompt_tokens: Decimal = Decimal("0.00015")
    agent_cost_per_1k_completion_tokens: Decimal = Decimal("0.0006")


@lru_cache
def get_settings() -> Settings:
    return Settings()

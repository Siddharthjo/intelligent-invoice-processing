from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg://invoice_app:invoice_app@localhost:5432/invoice_processing"

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

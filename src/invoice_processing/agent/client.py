from functools import lru_cache

from openai import OpenAI

from invoice_processing.config import get_settings


class AgentNotConfiguredError(Exception):
    """Raised when OPENAI_API_KEY is not configured."""


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise AgentNotConfiguredError("OPENAI_API_KEY is not set; the agent layer is not configured.")
    return OpenAI(api_key=settings.openai_api_key)

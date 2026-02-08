"""
Base class for all financial tools.

Security: Brokered Credentials pattern — LLM never sees API keys.
Reliability: Retry with exponential backoff + jitter, rate limit handling.
"""

import logging
import os
import time
from typing import Optional

import httpx
import yaml
from crewai.tools import BaseTool
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Credential Broker
# ──────────────────────────────────────────────────────────

class CredentialBroker:
    """
    Brokered Credentials pattern.

    LLM/agent NEVER sees API keys.
    Keys come from env vars and are injected at Tool level,
    bypassing the agent context entirely.
    """

    _REGISTRY = {
        "tbank": {
            "api_key": "TBANK_API_KEY",
            "client_id": "TBANK_CLIENT_ID",
            "base_url": "https://business.tbank.ru/openapi",
        },
        "tbc": {
            "api_key": "TBC_API_KEY",
            "base_url": "https://api.tbcbank.ge/v1",
        },
        "vakifbank": {
            "api_key": "VAKIFBANK_API_KEY",
            "base_url": "https://apiportal.vakifbank.com.tr",
        },
        "krungsri": {
            "api_key": "KRUNGSRI_API_KEY",
            "base_url": "https://developers.krungsri.com",
        },
        "tribute": {
            "api_key": "TRIBUTE_API_KEY",
            "webhook_secret": "TRIBUTE_WEBHOOK_SECRET",
            "base_url": "https://api.tribute.tg/v1",
        },
        "stripe": {
            "api_key": "STRIPE_SECRET_KEY",
            "webhook_secret": "STRIPE_WEBHOOK_SECRET",
            "base_url": "https://api.stripe.com/v1",
        },
        "moralis": {
            "api_key": "MORALIS_API_KEY",
            "base_url": "https://deep-index.moralis.io/api/v2.2",
        },
        "helius": {
            "api_key": "HELIUS_API_KEY",
            "base_url": "https://api.helius.xyz/v0",
        },
        "tonapi": {
            "api_key": "TONAPI_KEY",
            "base_url": "https://tonapi.io/v2",
        },
        "coingecko": {
            "api_key": "COINGECKO_API_KEY",
            "base_url": "https://api.coingecko.com/api/v3",
        },
    }

    @classmethod
    def get(cls, service: str) -> dict:
        """Get credentials for a service. Raises if env vars missing."""
        template = cls._REGISTRY.get(service)
        if not template:
            raise ValueError(f"Unknown service: {service}")

        result = {"base_url": template["base_url"]}
        missing = []
        for key, env_var in template.items():
            if key == "base_url":
                continue
            value = os.environ.get(env_var)
            if value is None:
                missing.append(env_var)
            result[key] = value

        if missing:
            raise EnvironmentError(
                f"Missing env vars for {service}: {missing}"
            )
        return result

    @classmethod
    def is_configured(cls, service: str) -> bool:
        """Check if a service has all required env vars set."""
        try:
            cls.get(service)
            return True
        except (ValueError, EnvironmentError):
            return False


# ──────────────────────────────────────────────────────────
# Financial Sources Config
# ──────────────────────────────────────────────────────────

def load_financial_config() -> dict:
    """Load financial config from env var or YAML file."""
    # Prefer env var (for Railway where config file is gitignored)
    env_config = os.getenv("FINANCIAL_CONFIG_YAML")
    if env_config:
        try:
            return yaml.safe_load(env_config) or {}
        except Exception:
            pass
    paths = [
        "/app/config/financial_sources.yaml",
        "config/financial_sources.yaml",
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


# ──────────────────────────────────────────────────────────
# Base Financial Tool
# ──────────────────────────────────────────────────────────

class FinancialBaseTool(BaseTool):
    """
    Base class for all financial tools.

    Built-in:
    - Brokered credentials (CredentialBroker)
    - Retry with exponential backoff + jitter (up to 3 attempts)
    - Rate limit handling (429 → wait Retry-After)
    - Logging (no secrets!)
    """

    service_name: str = ""

    def _get_credentials(self) -> dict:
        """Get credentials for this tool's service."""
        return CredentialBroker.get(self.service_name)

    def _get_client(self) -> httpx.Client:
        """Create an HTTP client with auth headers."""
        creds = self._get_credentials()
        headers = {"Content-Type": "application/json"}
        api_key = creds.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return httpx.Client(
            base_url=creds.get("base_url", ""),
            headers=headers,
            timeout=30.0,
        )

    def _request(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        **kwargs,
    ) -> dict:
        """
        Make an HTTP request with retry and rate-limit handling.

        Args:
            method: HTTP method (get, post, etc.)
            path: URL path relative to base_url
            max_retries: Max retry attempts
            **kwargs: Passed to httpx request
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                client = self._get_client()
                response = getattr(client, method)(path, **kwargs)

                if response.status_code == 429:
                    wait_time = int(
                        response.headers.get("Retry-After", 60)
                    )
                    logger.warning(
                        f"[{self.service_name}] Rate limited, "
                        f"waiting {wait_time}s (attempt {attempt})"
                    )
                    time.sleep(min(wait_time, 120))
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(
                    f"[{self.service_name}] HTTP {e.response.status_code} "
                    f"on {method.upper()} {path} (attempt {attempt})"
                )
                if e.response.status_code in (401, 403):
                    raise  # Don't retry auth errors
                if attempt < max_retries:
                    wait = min(2 ** attempt + 1, 30)
                    time.sleep(wait)

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_error = e
                logger.warning(
                    f"[{self.service_name}] Connection error: {e} "
                    f"(attempt {attempt})"
                )
                if attempt < max_retries:
                    wait = min(2 ** attempt + 1, 30)
                    time.sleep(wait)

            finally:
                try:
                    client.close()
                except Exception:
                    pass

        raise last_error or Exception(
            f"[{self.service_name}] Request failed after {max_retries} attempts"
        )

    def _safe_run(self, func, *args, **kwargs) -> str:
        """Wrap tool execution with error handling."""
        try:
            if not CredentialBroker.is_configured(self.service_name):
                return (
                    f"⚠️ {self.service_name} не настроен. "
                    f"Установите переменные окружения. "
                    f"Данные из этого источника временно недоступны."
                )
            return func(*args, **kwargs)
        except EnvironmentError as e:
            return f"⚠️ Нет доступа к {self.service_name}: {e}"
        except httpx.HTTPStatusError as e:
            return (
                f"⚠️ Ошибка API {self.service_name}: "
                f"HTTP {e.response.status_code}"
            )
        except Exception as e:
            logger.error(
                f"[{self.service_name}] Unexpected error: {e}",
                exc_info=True,
            )
            return f"⚠️ {self.service_name} временно недоступен: {type(e).__name__}"

"""Process configuration.

Everything the factory needs to boot lives here. Secrets do not: they are
resolved lazily through `vault.py` so they never land in a run record or a log
line. What this module holds are *pointers* to secrets, not the secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Australian entity: storage must stay onshore. These are the regions we accept
# without an explicit override, across the three providers we might deploy to.
AU_REGIONS = frozenset(
    {
        "ap-southeast-2",  # AWS Sydney
        "ap-southeast-4",  # AWS Melbourne
        "australia-southeast1",  # GCP Sydney
        "australia-southeast2",  # GCP Melbourne
        "australiaeast",  # Azure
        "australiasoutheast",
        "local",  # developer machine — no hosted storage involved
    }
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    pass


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is not None:
        value = value.strip()
    return value or None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class LLMSettings:
    """Model routing. Opus is the default because the agents that matter —
    offer synthesis, content specificity judging — are judgement calls."""

    model: str = field(default_factory=lambda: _env("PF_MODEL", "claude-opus-5"))
    cheap_model: str = field(
        default_factory=lambda: _env("PF_CHEAP_MODEL", "claude-haiku-4-5")
    )
    effort: str = field(default_factory=lambda: _env("PF_EFFORT", "high"))
    max_tokens: int = field(default_factory=lambda: _env_int("PF_MAX_TOKENS", 16000))
    # Only sent when set. Anthropic's residency values are a fixed enum; we do
    # not guess one — an operator supplies the value their account supports.
    inference_geo: str | None = field(
        default_factory=lambda: _env("PF_INFERENCE_GEO")
    )
    api_key_ref: str = field(
        default_factory=lambda: _env("PF_ANTHROPIC_KEY_REF", "env:ANTHROPIC_API_KEY")
    )


@dataclass(frozen=True)
class ScrapeSettings:
    user_agent: str = field(
        default_factory=lambda: _env(
            "PF_USER_AGENT",
            "ProductFactory/1.0 (+https://example.com.au/bot; contact@example.com.au)",
        )
    )
    requests_per_minute: float = field(
        default_factory=lambda: float(_env("PF_SCRAPE_RPM", "20"))
    )
    max_retries: int = field(default_factory=lambda: _env_int("PF_SCRAPE_RETRIES", 5))
    timeout_seconds: float = field(
        default_factory=lambda: float(_env("PF_SCRAPE_TIMEOUT", "20"))
    )
    respect_robots: bool = field(
        default_factory=lambda: _env_bool("PF_RESPECT_ROBOTS", True)
    )
    # When set, sources read from captured JSON fixtures instead of the network.
    # This is how the acceptance criteria stay runnable without live creds.
    fixtures_dir: str | None = field(default_factory=lambda: _env("PF_FIXTURES_DIR"))


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env(
            "PF_DATABASE_URL", f"sqlite:///{REPO_ROOT / 'var' / 'factory.db'}"
        )
    )
    data_region: str = field(default_factory=lambda: _env("PF_DATA_REGION", "local"))
    allow_offshore_storage: bool = field(
        default_factory=lambda: _env_bool("PF_ALLOW_OFFSHORE_STORAGE", False)
    )
    artifacts_dir: Path = field(
        default_factory=lambda: Path(
            _env("PF_ARTIFACTS_DIR", str(REPO_ROOT / "var" / "artifacts"))
        )
    )
    prompts_dir: Path = field(
        default_factory=lambda: Path(
            _env("PF_PROMPTS_DIR", str(REPO_ROOT / "prompts"))
        )
    )
    apps_dir: Path = field(
        default_factory=lambda: Path(
            _env("PF_APPS_DIR", str(REPO_ROOT / "var" / "apps"))
        )
    )
    base_url: str = field(
        default_factory=lambda: _env("PF_BASE_URL", "http://localhost:8000")
    )
    app_domain: str = field(
        default_factory=lambda: _env("PF_APP_DOMAIN", "apps.localhost")
    )
    storefront_adapter: str = field(
        default_factory=lambda: _env("PF_STOREFRONT", "selfhosted")
    )
    currency: str = field(default_factory=lambda: _env("PF_CURRENCY", "AUD"))
    operator_token_ref: str = field(
        default_factory=lambda: _env("PF_OPERATOR_TOKEN_REF", "env:PF_OPERATOR_TOKEN")
    )
    llm: LLMSettings = field(default_factory=LLMSettings)
    scrape: ScrapeSettings = field(default_factory=ScrapeSettings)

    def validate(self) -> None:
        """Fail loudly at boot rather than quietly storing AU customer data
        in Virginia."""
        if self.data_region not in AU_REGIONS and not self.allow_offshore_storage:
            raise ConfigError(
                f"PF_DATA_REGION={self.data_region!r} is not an Australian region. "
                f"Accepted: {sorted(AU_REGIONS)}. Set PF_ALLOW_OFFSHORE_STORAGE=1 "
                "to override deliberately."
            )
        for path in (self.artifacts_dir, self.apps_dir):
            path.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url[len("sqlite:///") :]).parent.mkdir(
                parents=True, exist_ok=True
            )


_settings: Settings | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        cfg = Settings()
        cfg.validate()
        _settings = cfg
    return _settings


def reset_settings() -> None:
    """Test hook — drops the memoised singleton."""
    global _settings
    _settings = None

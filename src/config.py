"""Environment-backed configuration for the Usertour client."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional: load a local .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


@dataclass
class Config:
    token: str
    base_url: str = "https://api.usertour.io"
    project_id: str | None = None
    default_theme_id: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ.get("USERTOUR_API_TOKEN", "").strip()
        if not token:
            raise SystemExit(
                "USERTOUR_API_TOKEN is not set. "
                "Copy .env.example to .env and fill it in."
            )
        return cls(
            token=token,
            base_url=os.environ.get(
                "USERTOUR_BASE_URL", "https://api.usertour.io"
            ).rstrip("/"),
            project_id=os.environ.get("USERTOUR_PROJECT_ID", "").strip() or None,
            default_theme_id=os.environ.get("USERTOUR_DEFAULT_THEME_ID", "").strip()
            or None,
        )

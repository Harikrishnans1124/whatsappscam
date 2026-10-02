"""Configuration loader for TrustShop AI."""

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"

def load_settings(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load settings from YAML file with environment variable fallbacks."""
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    
    config: dict[str, Any] = {}
    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Environment variable overrides
    db_url = os.getenv("DATABASE_URL", "sqlite:///data/trustshop.db")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    hmac_secret = os.getenv("HMAC_SECRET", "default-dev-hmac-secret-change-me")
    admin_api_key = os.getenv("ADMIN_API_KEY", "default-dev-admin-key-change-me")

    config["database_url"] = db_url
    config["redis_url"] = redis_url
    config["hmac_secret"] = hmac_secret
    config["admin_api_key"] = admin_api_key

    return config

settings = load_settings()

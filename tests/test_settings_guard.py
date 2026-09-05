"""
Tests for the production guard on JWT_SECRET_KEY in config.settings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DEFAULT_JWT_SECRET, Settings  # noqa: E402

REAL_SECRET = "x" * 32


def build(**overrides) -> Settings:
    """Build Settings ignoring any local .env so the test sees only its overrides."""
    return Settings(_env_file=None, **overrides)


class TestJWTSecretGuard:
    def test_development_allows_default_secret(self):
        s = build(ENV="development")
        assert s.JWT_SECRET_KEY == DEFAULT_JWT_SECRET

    def test_default_env_is_development(self):
        assert build().ENV == "development"

    @pytest.mark.parametrize("env", ["production", "prod", "Production", " PROD "])
    def test_production_rejects_default_secret(self, env):
        with pytest.raises(ValidationError, match="still the default placeholder"):
            build(ENV=env, JWT_SECRET_KEY=DEFAULT_JWT_SECRET)

    def test_production_rejects_short_secret(self):
        with pytest.raises(ValidationError, match="at least 32 characters"):
            build(ENV="production", JWT_SECRET_KEY="too-short")

    def test_production_accepts_real_secret(self):
        s = build(ENV="production", JWT_SECRET_KEY=REAL_SECRET)
        assert s.JWT_SECRET_KEY == REAL_SECRET

    def test_development_allows_short_secret(self):
        assert build(ENV="development", JWT_SECRET_KEY="short").JWT_SECRET_KEY == "short"

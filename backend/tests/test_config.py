"""Tests for FEAT-001: JWT secret hardening (fail-closed in production).

Covers:
- Production without JWT_SECRET raises ValueError at boot.
- Dev without JWT_SECRET generates an ephemeral secret (secrets.token_urlsafe).
- Empty JWT_SECRET ("") is treated as absent (same as None).
"""

import pytest

from app.core.config import Settings, get_settings


def _reload_settings(monkeypatch, env_overrides: dict) -> Settings:
    """Force a fresh Settings() with controlled env, bypassing the lru_cache.

    Only clears the get_settings() lru_cache and patched env — never reloads the
    config module, to avoid breaking other tests that already imported Settings.
    """
    for key, value in env_overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return Settings()


def test_settings_raises_without_secret_in_production(monkeypatch):
    """GIVEN is_production True and JWT_SECRET absent, WHEN settings load,
    THEN ValueError is raised (app refuses to boot)."""
    with pytest.raises(ValueError):
        _reload_settings(
            monkeypatch,
            {"ENVIRONMENT": "production", "JWT_SECRET": None},
        )


def test_settings_dev_generates_ephemeral_secret(monkeypatch):
    """GIVEN dev env without JWT_SECRET, WHEN settings load,
    THEN an ephemeral non-empty secret is generated."""
    settings = _reload_settings(
        monkeypatch,
        {"ENVIRONMENT": "development", "JWT_SECRET": None},
    )
    assert settings.jwt_secret is not None
    assert settings.jwt_secret.strip() != ""
    # Ephemeral secret must be reasonably strong (>= 32 url-safe chars).
    assert len(settings.jwt_secret) >= 32


def test_settings_empty_secret_treated_as_absent_in_dev(monkeypatch):
    """GIVEN dev env with JWT_SECRET="" (empty), WHEN settings load,
    THEN an ephemeral secret is generated (empty == absent)."""
    settings = _reload_settings(
        monkeypatch,
        {"ENVIRONMENT": "development", "JWT_SECRET": ""},
    )
    assert settings.jwt_secret is not None
    assert settings.jwt_secret.strip() != ""


def test_settings_explicit_secret_preserved(monkeypatch):
    """GIVEN a real JWT_SECRET in any env, WHEN settings load,
    THEN the exact secret is preserved (not regenerated)."""
    settings = _reload_settings(
        monkeypatch,
        {"ENVIRONMENT": "production", "JWT_SECRET": "super-secret-from-env-123"},
    )
    assert settings.jwt_secret == "super-secret-from-env-123"

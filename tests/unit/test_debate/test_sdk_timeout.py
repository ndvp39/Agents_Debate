"""Tests for the provider-aware watchdog timeout resolver in debate.sdk.sdk."""

import json

from debate.sdk.sdk import _resolve_watchdog_timeout


def _write_setup(tmp_path, data):
    """Write a setup.json under tmp_path and monkey-patch the resolver's path."""
    path = tmp_path / "setup.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _patch_path(monkeypatch, path):
    monkeypatch.setattr("debate.sdk.sdk._CONFIG_SETUP_PATH", path)


def test_explicit_arg_wins_over_everything(monkeypatch, tmp_path):
    path = _write_setup(tmp_path, {"debate": {"timeout_seconds": 90}})
    _patch_path(monkeypatch, path)
    assert _resolve_watchdog_timeout(42.0) == 42.0


def test_provider_specific_anthropic_picks_150(monkeypatch, tmp_path):
    path = _write_setup(tmp_path, {
        "provider": {
            "active": "gemini",
            "gemini": {"timeout_seconds": 90},
            "anthropic": {"timeout_seconds": 150},
        },
        "debate": {"timeout_seconds": 90},
    })
    _patch_path(monkeypatch, path)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert _resolve_watchdog_timeout(None) == 150.0


def test_provider_specific_gemini_picks_90(monkeypatch, tmp_path):
    path = _write_setup(tmp_path, {
        "provider": {
            "active": "gemini",
            "gemini": {"timeout_seconds": 90},
            "anthropic": {"timeout_seconds": 150},
        },
        "debate": {"timeout_seconds": 999},
    })
    _patch_path(monkeypatch, path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert _resolve_watchdog_timeout(None) == 90.0


def test_falls_back_to_global_when_no_provider_override(monkeypatch, tmp_path):
    path = _write_setup(tmp_path, {
        "provider": {"active": "gemini", "gemini": {}, "anthropic": {}},
        "debate": {"timeout_seconds": 120},
    })
    _patch_path(monkeypatch, path)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert _resolve_watchdog_timeout(None) == 120.0


def test_falls_back_to_hardcoded_when_setup_missing(monkeypatch, tmp_path):
    _patch_path(monkeypatch, tmp_path / "does_not_exist.json")
    assert _resolve_watchdog_timeout(None) == 90.0  # _DEFAULT_WATCHDOG_TIMEOUT

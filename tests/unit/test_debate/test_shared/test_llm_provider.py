"""Tests for debate.shared.llm_provider — provider selection and callable factories."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from debate.shared.llm_provider import (
    get_active_provider,
    make_debater_llm,
    make_judge_evaluate_llm,
    make_judge_route_llm,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _setup(active="anthropic"):
    return {
        "provider": {
            "active": active,
            "anthropic": {
                "debater_model": "claude-test",
                "judge_model": "claude-test",
                "temperature": 0.5,
                "max_tokens": 256,
            },
            "gemini": {
                "debater_model": "gemini-test",
                "judge_model": "gemini-test",
                "temperature": 0.5,
                "max_tokens": 256,
            },
        }
    }


# ---------------------------------------------------------------------------
# get_active_provider
# ---------------------------------------------------------------------------

def test_reads_active_from_config():
    assert get_active_provider(_setup("anthropic")) == "anthropic"
    assert get_active_provider(_setup("gemini")) == "gemini"


def test_env_var_overrides_config(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert get_active_provider(_setup("anthropic")) == "gemini"


def test_env_var_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "GEMINI")
    assert get_active_provider(_setup("anthropic")) == "gemini"


def test_defaults_to_anthropic_when_no_config():
    assert get_active_provider({}) == "anthropic"


def test_empty_env_var_falls_back_to_config(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "")
    assert get_active_provider(_setup("gemini")) == "gemini"


# ---------------------------------------------------------------------------
# make_debater_llm — Anthropic
# ---------------------------------------------------------------------------

def test_make_debater_llm_anthropic_returns_callable():
    with patch("anthropic.Anthropic"):
        llm = make_debater_llm(_setup("anthropic"))
    assert callable(llm)


def test_make_debater_llm_anthropic_calls_api():
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="answer")]
    with patch("anthropic.Anthropic", return_value=mock_client):
        llm = make_debater_llm(_setup("anthropic"))
    result = llm("test prompt")
    assert result == "answer"
    mock_client.messages.create.assert_called_once()


# ---------------------------------------------------------------------------
# make_debater_llm — Gemini
# ---------------------------------------------------------------------------

def test_make_debater_llm_gemini_returns_callable(monkeypatch):
    mock_genai = MagicMock()
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)
    llm = make_debater_llm(_setup("gemini"))
    assert callable(llm)


def test_make_debater_llm_gemini_calls_api(monkeypatch):
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "gemini answer"
    mock_genai.GenerativeModel.return_value = mock_model
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)
    llm = make_debater_llm(_setup("gemini"))
    result = llm("test prompt")
    assert result == "gemini answer"


# ---------------------------------------------------------------------------
# make_judge_evaluate_llm
# ---------------------------------------------------------------------------

def test_make_judge_evaluate_llm_anthropic_returns_dict():
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text='{"logical_consistency": 0.8, "citation_strength": 0.7, "rhetoric_quality": 0.9}')
    ]
    with patch("anthropic.Anthropic", return_value=mock_client):
        evaluate = make_judge_evaluate_llm(_setup("anthropic"))
    result = evaluate("great argument", ["source1"])
    assert result["logical_consistency"] == pytest.approx(0.8)
    assert result["citation_strength"] == pytest.approx(0.7)
    assert result["rhetoric_quality"] == pytest.approx(0.9)


def test_make_judge_evaluate_llm_gemini_returns_dict(monkeypatch):
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = (
        '{"logical_consistency": 0.6, "citation_strength": 0.5, "rhetoric_quality": 0.7}'
    )
    mock_genai.GenerativeModel.return_value = mock_model
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)
    evaluate = make_judge_evaluate_llm(_setup("gemini"))
    result = evaluate("argument text", ["cite"])
    assert "logical_consistency" in result
    assert "citation_strength" in result
    assert "rhetoric_quality" in result


# ---------------------------------------------------------------------------
# make_judge_route_llm
# ---------------------------------------------------------------------------

def test_make_judge_route_llm_anthropic_returns_string():
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="good feedback")]
    with patch("anthropic.Anthropic", return_value=mock_client):
        route = make_judge_route_llm(_setup("anthropic"))
    score = MagicMock(logical_consistency=0.8, citation_strength=0.7, rhetoric_quality=0.9)
    result = route(score)
    assert result == "good feedback"


def test_make_judge_route_llm_gemini_returns_string(monkeypatch):
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "gemini feedback"
    mock_genai.GenerativeModel.return_value = mock_model
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)
    route = make_judge_route_llm(_setup("gemini"))
    score = MagicMock(logical_consistency=0.5, citation_strength=0.6, rhetoric_quality=0.7)
    result = route(score)
    assert result == "gemini feedback"

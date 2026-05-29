"""Tests for debate.shared.llm_provider — provider selection and callable factories."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from debate.shared.llm_provider import (
    _is_daily_quota,
    _is_rate_limit,
    _retry,
    _suggested_delay,
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


def _mock_gemini_client():
    """Return a MagicMock that satisfies _gemini_client() + google.genai.types imports."""
    return MagicMock()


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

def test_make_debater_llm_gemini_returns_callable():
    mock_types = MagicMock()
    with patch.dict(sys.modules, {"google.genai": MagicMock(), "google.genai.types": mock_types}), \
         patch("debate.shared.llm_gemini._gemini_client", return_value=_mock_gemini_client()):
        llm = make_debater_llm(_setup("gemini"))
    assert callable(llm)


def test_make_debater_llm_gemini_calls_api():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "gemini answer"
    mock_types = MagicMock()
    with patch.dict(sys.modules, {"google.genai": MagicMock(), "google.genai.types": mock_types}), \
         patch("debate.shared.llm_gemini._gemini_client", return_value=mock_client):
        llm = make_debater_llm(_setup("gemini"))
    result = llm("test prompt")
    assert result == "gemini answer"


# ---------------------------------------------------------------------------
# make_judge_evaluate_llm
# ---------------------------------------------------------------------------

def test_debater_llm_routes_through_gatekeeper_when_provided():
    """When a gatekeeper is supplied, every API call goes through `gatekeeper.execute(...)`
    and the response's usage info is recorded — no bypass possible."""
    mock_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="argument body")]
    fake_response.usage.input_tokens = 123
    fake_response.usage.output_tokens = 45
    mock_client.messages.create.return_value = fake_response

    gk = MagicMock()
    gk.execute.side_effect = lambda fn: fn()  # pass-through so the real client_call runs

    with patch("anthropic.Anthropic", return_value=mock_client):
        llm = make_debater_llm(_setup("anthropic"), gatekeeper=gk)
    result = llm("prompt text")

    assert result == "argument body"
    gk.execute.assert_called_once()  # gate was used
    gk.record_tokens.assert_called_once_with(123, 45)  # real usage forwarded
    mock_client.messages.create.assert_called_once()  # client called exactly once via the gate


def test_judge_evaluate_llm_routes_through_gatekeeper():
    mock_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(
        text='{"logical_consistency": 0.8, "citation_strength": 0.7, "rhetoric_quality": 0.9}'
    )]
    fake_response.usage.input_tokens = 200
    fake_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = fake_response

    gk = MagicMock()
    gk.execute.side_effect = lambda fn: fn()

    with patch("anthropic.Anthropic", return_value=mock_client):
        evaluate = make_judge_evaluate_llm(_setup("anthropic"), gatekeeper=gk)
    out = evaluate("scoring prompt")
    assert out["logical_consistency"] == pytest.approx(0.8)
    gk.execute.assert_called_once()
    gk.record_tokens.assert_called_once_with(200, 50)


def test_make_judge_evaluate_llm_anthropic_returns_dict():
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text='{"logical_consistency": 0.8, "citation_strength": 0.7, "rhetoric_quality": 0.9}')
    ]
    with patch("anthropic.Anthropic", return_value=mock_client):
        evaluate = make_judge_evaluate_llm(_setup("anthropic"))
    # The prompt is now rendered by the evaluate_persuasion_score skill — the
    # wrapper just forwards a single string to the API.
    rendered_prompt = (
        "You are an impartial, stateless debate judge. ... Score this argument.\n"
        "great argument\nCitations: ['source1']\n"
        "Reply with ONLY a raw JSON object."
    )
    result = evaluate(rendered_prompt)
    assert result["logical_consistency"] == pytest.approx(0.8)
    assert result["citation_strength"] == pytest.approx(0.7)
    assert result["rhetoric_quality"] == pytest.approx(0.9)


def test_make_judge_evaluate_llm_gemini_returns_dict():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = (
        '{"logical_consistency": 0.6, "citation_strength": 0.5, "rhetoric_quality": 0.7}'
    )
    mock_types = MagicMock()
    with patch.dict(sys.modules, {"google.genai": MagicMock(), "google.genai.types": mock_types}), \
         patch("debate.shared.llm_gemini._gemini_client", return_value=mock_client):
        evaluate = make_judge_evaluate_llm(_setup("gemini"))
    rendered_prompt = (
        "You are an impartial, stateless debate judge. ... Score this argument.\n"
        "argument text\nCitations: ['cite']\n"
        "Reply with ONLY a raw JSON object."
    )
    result = evaluate(rendered_prompt)
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
    assert route(score) == "good feedback"


def test_make_judge_route_llm_gemini_returns_string():
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value.text = "gemini feedback"
    mock_types = MagicMock()
    with patch.dict(sys.modules, {"google.genai": MagicMock(), "google.genai.types": mock_types}), \
         patch("debate.shared.llm_gemini._gemini_client", return_value=mock_client):
        route = make_judge_route_llm(_setup("gemini"))
    score = MagicMock(logical_consistency=0.5, citation_strength=0.6, rhetoric_quality=0.7)
    assert route(score) == "gemini feedback"


# ---------------------------------------------------------------------------
# _is_rate_limit / _is_daily_quota / _suggested_delay
# ---------------------------------------------------------------------------

def test_is_rate_limit_detects_429():
    assert _is_rate_limit(Exception("429 RESOURCE_EXHAUSTED quota exceeded"))


def test_is_rate_limit_detects_class_name():
    class RateLimitError(Exception):
        pass
    assert _is_rate_limit(RateLimitError("too many requests"))


def test_is_rate_limit_false_for_other_errors():
    assert not _is_rate_limit(ValueError("bad input"))


def test_is_daily_quota_detects_per_day():
    assert _is_daily_quota(Exception("429 GenerateRequestsPerDayPerProjectPerModel quota exceeded"))


def test_is_daily_quota_false_for_per_minute():
    assert not _is_daily_quota(Exception("429 GenerateRequestsPerMinutePerProjectPerModel limit"))


def test_suggested_delay_parses_retry_in():
    exc = Exception("You exceeded quota. Please retry in 14.3s.")
    delay = _suggested_delay(exc)
    assert delay == pytest.approx(16.3)  # 14.3 + 2 buffer


def test_suggested_delay_parses_retry_delay_json():
    exc = Exception('details: [{"retryDelay": "30s"}]')
    delay = _suggested_delay(exc)
    assert delay == pytest.approx(32.0)  # 30 + 2 buffer


def test_suggested_delay_returns_none_when_absent():
    assert _suggested_delay(Exception("some other error")) is None


# ---------------------------------------------------------------------------
# _retry — smart behaviour
# ---------------------------------------------------------------------------

def test_retry_succeeds_on_first_try():
    fn = MagicMock(return_value="ok")
    assert _retry(fn) == "ok"
    fn.assert_called_once()


def test_retry_raises_immediately_on_daily_quota():
    fn = MagicMock(side_effect=Exception("429 PerDay quota limit reached"))
    with pytest.raises(RuntimeError, match="tomorrow"):
        _retry(fn)
    fn.assert_called_once()  # no retries — fails fast


def test_retry_waits_suggested_delay_for_per_minute_limit(monkeypatch):
    calls = []
    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise Exception("429 RESOURCE_EXHAUSTED. Please retry in 5s.")
        return "done"

    slept = []
    monkeypatch.setattr("debate.shared.llm_retry.time.sleep", lambda s: slept.append(s))
    result = _retry(fn)
    assert result == "done"
    assert len(calls) == 3
    assert all(s == pytest.approx(7.0) for s in slept)  # 5 + 2 buffer each


def test_retry_uses_exponential_backoff_for_non_rate_limit(monkeypatch):
    fn = MagicMock(side_effect=[ValueError("bad"), ValueError("bad"), "ok"])
    slept = []
    monkeypatch.setattr("debate.shared.llm_retry.time.sleep", lambda s: slept.append(s))
    result = _retry(fn)
    assert result == "ok"
    assert slept[0] == pytest.approx(5.0)
    assert slept[1] == pytest.approx(10.0)


def test_retry_re_raises_after_max_retries(monkeypatch):
    fn = MagicMock(side_effect=ConnectionError("network down"))
    monkeypatch.setattr("debate.shared.llm_retry.time.sleep", lambda s: None)
    with pytest.raises(ConnectionError):
        _retry(fn)


def test_retry_retries_on_empty_string_then_succeeds(monkeypatch):
    fn = MagicMock(side_effect=["", "", "good response"])
    slept = []
    monkeypatch.setattr("debate.shared.llm_retry.time.sleep", lambda s: slept.append(s))
    result = _retry(fn)
    assert result == "good response"
    assert fn.call_count == 3
    assert all(s == pytest.approx(2.0) for s in slept)


def test_retry_retries_on_none_response_then_succeeds(monkeypatch):
    fn = MagicMock(side_effect=[None, "valid"])
    monkeypatch.setattr("debate.shared.llm_retry.time.sleep", lambda s: None)
    result = _retry(fn)
    assert result == "valid"
    assert fn.call_count == 2


def test_retry_raises_after_max_empty_retries(monkeypatch):
    fn = MagicMock(return_value="")
    monkeypatch.setattr("debate.shared.llm_retry.time.sleep", lambda s: None)
    with pytest.raises(ValueError, match="empty response"):
        _retry(fn)
    assert fn.call_count == 4  # 1 initial + 3 empty retries

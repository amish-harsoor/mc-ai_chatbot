"""Tests for chat LLM provider selection (OpenAI primary + fallbacks)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config import _llm_provider_chain, configure_llm, create_llm


def test_llm_provider_chain_default_openai_first(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_FALLBACK_PROVIDERS", raising=False)
    assert _llm_provider_chain() == ["openai", "openrouter", "groq"]


def test_llm_provider_chain_primary_with_custom_fallbacks(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "groq,openrouter")
    assert _llm_provider_chain() == ["openai", "groq", "openrouter"]


def test_llm_provider_chain_auto(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("LLM_FALLBACK_PROVIDERS", raising=False)
    assert _llm_provider_chain() == ["openai", "openrouter", "groq"]


def test_create_llm_unknown_provider():
    with pytest.raises(RuntimeError, match="Unknown LLM_PROVIDER"):
        create_llm("not-a-provider")


def test_configure_llm_uses_openai_when_available(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "openrouter,groq")
    fake = MagicMock(name="openai_llm")
    with patch("src.config._create_openai_llm", return_value=fake) as openai_mock, patch(
        "src.config._create_openrouter_llm"
    ) as or_mock, patch("src.config._create_groq_llm") as groq_mock, patch(
        "src.config.Settings"
    ) as settings:
        configure_llm()
        openai_mock.assert_called_once()
        or_mock.assert_not_called()
        groq_mock.assert_not_called()
        assert settings.llm is fake


def test_configure_llm_falls_back_when_openai_fails(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "openrouter,groq")
    fake = MagicMock(name="openrouter_llm")
    with patch(
        "src.config._create_openai_llm",
        side_effect=RuntimeError("OPENAI_API_KEY is required"),
    ), patch("src.config._create_openrouter_llm", return_value=fake) as or_mock, patch(
        "src.config._create_groq_llm"
    ) as groq_mock, patch("src.config.Settings") as settings:
        configure_llm()
        or_mock.assert_called_once()
        groq_mock.assert_not_called()
        assert settings.llm is fake


def test_configure_llm_falls_through_to_groq(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "openrouter,groq")
    fake = MagicMock(name="groq_llm")
    with patch(
        "src.config._create_openai_llm",
        side_effect=RuntimeError("no openai key"),
    ), patch(
        "src.config._create_openrouter_llm",
        side_effect=RuntimeError("no openrouter key"),
    ), patch("src.config._create_groq_llm", return_value=fake), patch(
        "src.config.Settings"
    ) as settings:
        configure_llm()
        assert settings.llm is fake


def test_configure_llm_all_fail(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "openrouter,groq")
    with patch(
        "src.config._create_openai_llm",
        side_effect=RuntimeError("no openai"),
    ), patch(
        "src.config._create_openrouter_llm",
        side_effect=RuntimeError("no openrouter"),
    ), patch(
        "src.config._create_groq_llm",
        side_effect=RuntimeError("no groq"),
    ), patch("src.config.Settings"):
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            configure_llm()

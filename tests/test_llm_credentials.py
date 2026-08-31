"""
Tests for per-request LLM credentials.

Callers (an API request carrying the user's own OpenAI key) can bind a key and
model for the duration of a pipeline run without anything being persisted.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.llm_tools import get_llm, llm_credentials, resolve_credentials


@pytest.fixture
def settings_without_key():
    """Settings with no server-side key configured."""
    ms = MagicMock()
    ms.OPENAI_API_KEY = ""
    ms.OPENAI_MODEL = "gpt-4o"
    with patch("config.settings.settings", ms):
        yield ms


@pytest.fixture
def settings_with_key():
    """Settings with a server-side fallback key configured."""
    ms = MagicMock()
    ms.OPENAI_API_KEY = "sk-server-fallback"
    ms.OPENAI_MODEL = "gpt-4o"
    with patch("config.settings.settings", ms):
        yield ms


class TestResolveCredentials:
    """Precedence between caller-supplied credentials and settings."""

    def test_falls_back_to_settings(self, settings_with_key):
        assert resolve_credentials() == ("sk-server-fallback", "gpt-4o")

    def test_caller_key_wins(self, settings_with_key):
        with llm_credentials(api_key="sk-user", model="gpt-4o-mini"):
            assert resolve_credentials() == ("sk-user", "gpt-4o-mini")

    def test_model_alone_keeps_settings_key(self, settings_with_key):
        with llm_credentials(model="o4-mini"):
            assert resolve_credentials() == ("sk-server-fallback", "o4-mini")

    def test_key_alone_keeps_settings_model(self, settings_with_key):
        with llm_credentials(api_key="sk-user"):
            assert resolve_credentials() == ("sk-user", "gpt-4o")

    def test_user_key_works_without_server_key(self, settings_without_key):
        with llm_credentials(api_key="sk-user"):
            assert resolve_credentials() == ("sk-user", "gpt-4o")


class TestCredentialScope:
    """Credentials must not leak outside the block that bound them."""

    def test_reset_after_block(self, settings_with_key):
        with llm_credentials(api_key="sk-user"):
            pass
        assert resolve_credentials() == ("sk-server-fallback", "gpt-4o")

    def test_reset_after_exception(self, settings_with_key):
        with pytest.raises(RuntimeError):
            with llm_credentials(api_key="sk-user"):
                raise RuntimeError("pipeline blew up")
        assert resolve_credentials() == ("sk-server-fallback", "gpt-4o")

    def test_nested_blocks_restore_outer(self, settings_with_key):
        with llm_credentials(api_key="sk-outer"):
            with llm_credentials(api_key="sk-inner"):
                assert resolve_credentials()[0] == "sk-inner"
            assert resolve_credentials()[0] == "sk-outer"

    def test_empty_block_is_a_no_op(self, settings_with_key):
        with llm_credentials(None, None):
            assert resolve_credentials() == ("sk-server-fallback", "gpt-4o")


class TestGetLLM:
    """get_llm builds the client from whichever credentials are in effect."""

    @pytest.fixture
    def fake_langchain(self):
        """Stub out langchain_openai so no real client is constructed."""
        module = MagicMock()
        with patch.dict(sys.modules, {"langchain_openai": module}):
            yield module

    def test_returns_none_without_any_key(self, settings_without_key, fake_langchain):
        assert get_llm() is None
        fake_langchain.ChatOpenAI.assert_not_called()

    def test_uses_caller_credentials(self, settings_with_key, fake_langchain):
        with llm_credentials(api_key="sk-user", model="gpt-4.1"):
            get_llm(temperature=0.3)

        _, kwargs = fake_langchain.ChatOpenAI.call_args
        assert kwargs["api_key"] == "sk-user"
        assert kwargs["model"] == "gpt-4.1"
        assert kwargs["temperature"] == 0.3

    def test_uses_settings_when_unbound(self, settings_with_key, fake_langchain):
        get_llm()

        _, kwargs = fake_langchain.ChatOpenAI.call_args
        assert kwargs["api_key"] == "sk-server-fallback"
        assert kwargs["model"] == "gpt-4o"

    def test_caller_key_alone_is_enough(self, settings_without_key, fake_langchain):
        with llm_credentials(api_key="sk-user"):
            assert get_llm() is not None

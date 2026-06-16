"""Tests for the chat command."""

import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from biotope.commands.chat import HAS_BIOCHATTER, chat


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


def test_chat_without_biochatter(runner):
    """Test that chat fails gracefully when biochatter is not installed."""
    with patch("biotope.commands.chat.HAS_BIOCHATTER", False):
        result = runner.invoke(chat)
        assert result.exit_code == 1
        assert "biochatter is not installed" in result.output


def test_chat_missing_api_key(runner):
    """Test that chat fails with a biotope-owned message when no API key is set."""
    with patch.dict(os.environ, {}, clear=True):
        result = runner.invoke(chat)
        assert result.exit_code == 1
        assert "No API key provided" in result.output
        assert "OPENAI_API_KEY" in result.output


@pytest.mark.skipif(not HAS_BIOCHATTER, reason="biochatter not installed")
class TestChatWithBiochatter:
    """Tests that require biochatter to be installed."""

    def test_chat_backend_failure_user_message(self, runner):
        """Backend exceptions are translated to biotope UX messages, not passed through."""
        with patch("biotope.commands.chat.GptConversation") as mock_gpt:
            mock_gpt.side_effect = RuntimeError("internal biochatter failure detail")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                result = runner.invoke(chat, ["--no-interactive"], input="test query")

        assert result.exit_code == 1
        assert "Chat session failed" in result.output
        assert "internal biochatter failure detail" not in result.output

    def test_chat_non_interactive(self, runner):
        """Test non-interactive chat mode."""
        mock_conversation = MagicMock()
        mock_conversation.query.return_value = ("Test response", None, None)

        with patch("biotope.commands.chat.GptConversation") as mock_gpt:
            mock_gpt.return_value = mock_conversation
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                result = runner.invoke(chat, ["--no-interactive"], input="test query")

                assert result.exit_code == 0
                assert "Test response" in result.output
                mock_conversation.query.assert_called_once_with("test query")

    def test_chat_interactive_exit(self, runner):
        """Test interactive chat mode with exit command."""
        mock_conversation = MagicMock()

        with patch("biotope.commands.chat.GptConversation") as mock_gpt:
            mock_gpt.return_value = mock_conversation
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                result = runner.invoke(chat, input="exit\n")

                assert result.exit_code == 0
                assert "Starting interactive chat session" in result.output
                mock_conversation.query.assert_not_called()

    def test_chat_with_options(self, runner):
        """Test chat with various options set."""
        mock_conversation = MagicMock()
        mock_conversation.query.return_value = ("Test response", None, None)

        with patch("biotope.commands.chat.GptConversation") as mock_gpt:
            mock_gpt.return_value = mock_conversation
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                result = runner.invoke(
                    chat,
                    [
                        "--model-name",
                        "test-model",
                        "--correct",
                        "--no-interactive",
                    ],
                    input="test query",
                )

                assert result.exit_code == 0
                assert "Test response" in result.output
                mock_gpt.assert_called_once_with(
                    model_name="test-model",
                    prompts=None,
                    correct=True,
                )

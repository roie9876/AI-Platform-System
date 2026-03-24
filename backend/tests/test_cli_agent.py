"""Unit tests for CLI agent commands."""

import json
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from cli.main import cli


def _mock_credentials():
    return ("http://localhost:8000", {"Authorization": "Bearer test"}, {})


class TestAgentList:
    def test_list_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "abc-123", "name": "Test Agent", "status": "active", "description": "A test agent"},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("cli.commands.agent.load_credentials", return_value=_mock_credentials()), \
             patch("cli.commands.agent.httpx.get", return_value=mock_response):
            runner = CliRunner()
            result = runner.invoke(cli, ["agent", "list"])
            assert result.exit_code == 0
            assert "Test Agent" in result.output

    def test_list_auth_expired(self):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("cli.commands.agent.load_credentials", return_value=_mock_credentials()), \
             patch("cli.commands.agent.httpx.get", return_value=mock_response):
            runner = CliRunner()
            result = runner.invoke(cli, ["agent", "list"])
            assert result.exit_code != 0

    def test_list_connection_error(self):
        import httpx
        with patch("cli.commands.agent.load_credentials", return_value=_mock_credentials()), \
             patch("cli.commands.agent.httpx.get", side_effect=httpx.ConnectError("refused")):
            runner = CliRunner()
            result = runner.invoke(cli, ["agent", "list"])
            assert result.exit_code != 0
            assert "Cannot connect" in result.output


class TestAgentRun:
    def test_run_success_streaming(self):
        # Mock thread creation
        thread_response = MagicMock()
        thread_response.status_code = 200
        thread_response.json.return_value = {"id": "thread-001"}
        thread_response.raise_for_status = MagicMock()

        # Mock SSE stream
        stream_context = MagicMock()
        stream_mock = MagicMock()
        stream_mock.status_code = 200
        stream_mock.raise_for_status = MagicMock()
        stream_mock.iter_lines.return_value = [
            'data: {"type": "content", "content": "Hello "}',
            'data: {"type": "content", "content": "World"}',
            "data: [DONE]",
        ]
        stream_context.__enter__ = MagicMock(return_value=stream_mock)
        stream_context.__exit__ = MagicMock(return_value=False)

        with patch("cli.commands.agent.load_credentials", return_value=_mock_credentials()), \
             patch("cli.commands.agent.httpx.post", return_value=thread_response), \
             patch("cli.commands.agent.httpx.stream", return_value=stream_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["agent", "run", "agent-001", "-m", "hi"])
            assert result.exit_code == 0
            assert "Hello " in result.output
            assert "World" in result.output

    def test_run_json_output(self):
        thread_response = MagicMock()
        thread_response.status_code = 200
        thread_response.json.return_value = {"id": "thread-001"}
        thread_response.raise_for_status = MagicMock()

        stream_context = MagicMock()
        stream_mock = MagicMock()
        stream_mock.status_code = 200
        stream_mock.raise_for_status = MagicMock()
        stream_mock.iter_lines.return_value = [
            'data: {"type": "content", "content": "Result"}',
            "data: [DONE]",
        ]
        stream_context.__enter__ = MagicMock(return_value=stream_mock)
        stream_context.__exit__ = MagicMock(return_value=False)

        with patch("cli.commands.agent.load_credentials", return_value=_mock_credentials()), \
             patch("cli.commands.agent.httpx.post", return_value=thread_response), \
             patch("cli.commands.agent.httpx.stream", return_value=stream_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["agent", "run", "agent-001", "-m", "hi", "--json-output"])
            assert result.exit_code == 0
            output = json.loads(result.output.strip())
            assert output["response"] == "Result"
            assert output["thread_id"] == "thread-001"

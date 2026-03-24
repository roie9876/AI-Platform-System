"""Unit tests for CLI auth commands."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from cli.main import cli
from cli.commands.auth import load_credentials


class TestAuthLogin:
    def test_login_success(self, tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test-token"}
        mock_response.cookies = {"session": "abc123"}
        mock_response.raise_for_status = MagicMock()

        with patch("cli.commands.auth.httpx.post", return_value=mock_response), \
             patch("cli.commands.auth.CONFIG_DIR", tmp_path), \
             patch("cli.commands.auth.CREDENTIALS_FILE", tmp_path / "credentials.json"):
            runner = CliRunner()
            result = runner.invoke(cli, ["auth", "login"], input="test@example.com\nsecret\n")
            assert result.exit_code == 0
            assert "Logged in as test@example.com" in result.output

    def test_login_http_error(self):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid credentials"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        with patch("cli.commands.auth.httpx.post", return_value=mock_response):
            runner = CliRunner()
            result = runner.invoke(cli, ["auth", "login"], input="test@example.com\nwrong\n")
            assert result.exit_code != 0

    def test_login_connection_error(self):
        import httpx
        with patch("cli.commands.auth.httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            runner = CliRunner()
            result = runner.invoke(cli, ["auth", "login"], input="test@example.com\nsecret\n")
            assert result.exit_code != 0
            assert "Cannot connect" in result.output


class TestLoadCredentials:
    def test_no_credentials_file(self, tmp_path):
        with patch("cli.commands.auth.CREDENTIALS_FILE", tmp_path / "nonexistent.json"):
            try:
                load_credentials()
                assert False, "Should have raised SystemExit"
            except SystemExit:
                pass

    def test_valid_credentials_file(self, tmp_path):
        cred_file = tmp_path / "credentials.json"
        cred_file.write_text(json.dumps({
            "base_url": "http://localhost:9000",
            "access_token": "my-token",
            "cookies": {"session": "val"},
        }))

        with patch("cli.commands.auth.CREDENTIALS_FILE", cred_file):
            base_url, headers, cookies = load_credentials()
            assert base_url == "http://localhost:9000"
            assert headers["Authorization"] == "Bearer my-token"
            assert cookies == {"session": "val"}

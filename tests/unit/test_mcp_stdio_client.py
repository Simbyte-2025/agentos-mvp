"""Unit tests for MCPStdioClient.

These tests use mocked subprocess to simulate MCP server responses
without any network or real process interaction.
"""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest

from agentos.integrations.mcp.stdio_client import (
    MCPStdioClient,
    DEFAULT_SERVER_COMMAND,
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RESPONSE_SIZE,
)
from agentos.integrations.mcp.exceptions import (
    MCPError,
    MCPTimeoutError,
    MCPConnectionError,
    MCPResponseError,
)


# =============================================================================
# Instantiation Tests
# =============================================================================

def test_client_instantiation_defaults():
    """Test MCPStdioClient uses correct defaults."""
    client = MCPStdioClient()
    
    assert client.server_command == DEFAULT_SERVER_COMMAND
    assert client.timeout == DEFAULT_TIMEOUT
    assert client.max_response_size == DEFAULT_MAX_RESPONSE_SIZE
    assert client.max_retries == 1


def test_client_instantiation_custom_config():
    """Test MCPStdioClient accepts custom configuration."""
    client = MCPStdioClient(
        server_command="custom-mcp-server",
        timeout=60,
        max_response_size=100_000,
        max_retries=3,
    )
    
    assert client.server_command == "custom-mcp-server"
    assert client.timeout == 60
    assert client.max_response_size == 100_000
    assert client.max_retries == 3


def test_client_env_var_override(monkeypatch):
    """Test MCPStdioClient reads from environment variables."""
    monkeypatch.setenv("MCP_SERVER_COMMAND", "env-mcp-server")
    monkeypatch.setenv("MCP_TIMEOUT", "45")
    
    client = MCPStdioClient()
    
    assert client.server_command == "env-mcp-server"
    assert client.timeout == 45


def test_client_explicit_overrides_env(monkeypatch):
    """Test explicit args override environment variables."""
    monkeypatch.setenv("MCP_SERVER_COMMAND", "env-server")
    monkeypatch.setenv("MCP_TIMEOUT", "99")
    
    client = MCPStdioClient(server_command="explicit-server", timeout=10)
    
    assert client.server_command == "explicit-server"
    assert client.timeout == 10


# =============================================================================
# JSON-RPC Envelope Tests
# =============================================================================

def test_build_request_jsonrpc_envelope():
    """Test that _build_request creates valid JSON-RPC 2.0 envelope."""
    client = MCPStdioClient()
    
    request = client._build_request("test_method", {"key": "value"})
    
    assert request["jsonrpc"] == "2.0"
    assert request["id"] == 1
    assert request["method"] == "test_method"
    assert request["params"] == {"key": "value"}


def test_build_request_increments_id():
    """Test that request IDs increment."""
    client = MCPStdioClient()
    
    req1 = client._build_request("method1", {})
    req2 = client._build_request("method2", {})
    req3 = client._build_request("method3", {})
    
    assert req1["id"] == 1
    assert req2["id"] == 2
    assert req3["id"] == 3


def test_parse_response_success():
    """Test parsing successful JSON-RPC response."""
    client = MCPStdioClient()
    client._request_id = 1  # Set expected ID
    
    response_text = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"data": "success"}
    })
    
    result = client._parse_response(response_text, request_id=1)
    
    assert result == {"data": "success"}


def test_parse_response_error():
    """Test parsing JSON-RPC error response."""
    client = MCPStdioClient()
    
    response_text = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32600,
            "message": "Invalid Request",
            "data": {"detail": "missing field"}
        }
    })
    
    with pytest.raises(MCPResponseError) as exc_info:
        client._parse_response(response_text, request_id=1)
    
    assert "Invalid Request" in str(exc_info.value)
    assert exc_info.value.code == -32600
    assert exc_info.value.data == {"detail": "missing field"}


def test_parse_response_invalid_json():
    """Test handling of invalid JSON response."""
    client = MCPStdioClient()
    
    with pytest.raises(MCPResponseError) as exc_info:
        client._parse_response("not valid json {{{", request_id=1)
    
    assert "Invalid JSON" in str(exc_info.value)


def test_parse_response_wrong_jsonrpc_version():
    """Test rejection of wrong JSON-RPC version."""
    client = MCPStdioClient()
    
    response_text = json.dumps({
        "jsonrpc": "1.0",
        "id": 1,
        "result": "data"
    })
    
    with pytest.raises(MCPResponseError) as exc_info:
        client._parse_response(response_text, request_id=1)
    
    assert "Invalid jsonrpc version" in str(exc_info.value)


def test_parse_response_id_mismatch():
    """Test rejection of mismatched request ID."""
    client = MCPStdioClient()
    
    response_text = json.dumps({
        "jsonrpc": "2.0",
        "id": 999,
        "result": "data"
    })
    
    with pytest.raises(MCPResponseError) as exc_info:
        client._parse_response(response_text, request_id=1)
    
    assert "ID mismatch" in str(exc_info.value)


def test_parse_response_missing_result():
    """Test rejection of response without result field."""
    client = MCPStdioClient()
    
    response_text = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
    })
    
    with pytest.raises(MCPResponseError) as exc_info:
        client._parse_response(response_text, request_id=1)
    
    assert "missing 'result'" in str(exc_info.value)


# =============================================================================
# Subprocess Call Tests
# =============================================================================

@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_success(mock_popen):
    """Test successful MCP call with mocked subprocess."""
    # Setup mock process
    mock_process = MagicMock()
    mock_process.communicate.return_value = (
        json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"search_results": ["result1", "result2"]}
        }),
        ""  # stderr
    )
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    # Execute
    client = MCPStdioClient()
    result = client.call("web_search", {"query": "test"})
    
    # Verify
    assert result == {"search_results": ["result1", "result2"]}
    mock_popen.assert_called_once()
    mock_process.communicate.assert_called_once()


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_sends_correct_jsonrpc_request(mock_popen):
    """Test that call() sends correctly formatted JSON-RPC request."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"}),
        ""
    )
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient()
    client.call("test_method", {"param1": "value1"})
    
    # Get the input sent to communicate()
    call_args = mock_process.communicate.call_args
    input_sent = call_args[1]["input"]
    
    # Parse and verify
    request = json.loads(input_sent.strip())
    assert request["jsonrpc"] == "2.0"
    assert request["id"] == 1
    assert request["method"] == "test_method"
    assert request["params"] == {"param1": "value1"}


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_timeout(mock_popen):
    """Test timeout handling."""
    import subprocess
    
    mock_process = MagicMock()
    mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=30)
    mock_process.kill = MagicMock()
    mock_process.wait = MagicMock()
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient(timeout=30, max_retries=0)  # No retries
    
    with pytest.raises(MCPTimeoutError) as exc_info:
        client.call("slow_method", {})
    
    assert "timed out" in str(exc_info.value)
    mock_process.kill.assert_called_once()


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_process_spawn_error(mock_popen):
    """Test handling of process spawn failure."""
    mock_popen.side_effect = OSError("Command not found")
    
    client = MCPStdioClient(max_retries=0)
    
    with pytest.raises(MCPConnectionError) as exc_info:
        client.call("method", {})
    
    assert "Failed to spawn" in str(exc_info.value)


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_retry_success(mock_popen):
    """Test that transient errors are retried and succeed."""
    import subprocess
    
    mock_process_fail = MagicMock()
    mock_process_fail.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=30)
    mock_process_fail.kill = MagicMock()
    mock_process_fail.wait = MagicMock()
    
    mock_process_success = MagicMock()
    mock_process_success.communicate.return_value = (
        json.dumps({"jsonrpc": "2.0", "id": 2, "result": "success"}),
        ""
    )
    mock_process_success.returncode = 0
    
    # First call fails, second succeeds
    mock_popen.side_effect = [mock_process_fail, mock_process_success]
    
    client = MCPStdioClient(max_retries=1)
    result = client.call("method", {})
    
    assert result == "success"
    assert mock_popen.call_count == 2


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_retry_exhausted(mock_popen):
    """Test that error is raised after retries exhausted."""
    import subprocess
    
    mock_process = MagicMock()
    mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=30)
    mock_process.kill = MagicMock()
    mock_process.wait = MagicMock()
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient(max_retries=2)  # 2 retries = 3 total attempts
    
    with pytest.raises(MCPTimeoutError):
        client.call("method", {})
    
    assert mock_popen.call_count == 3  # Initial + 2 retries


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_no_retry_on_response_error(mock_popen):
    """Test that MCPResponseError is not retried (not transient)."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = (
        json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid Request"}
        }),
        ""
    )
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient(max_retries=3)
    
    with pytest.raises(MCPResponseError):
        client.call("method", {})
    
    # Should only try once (no retry for response errors)
    assert mock_popen.call_count == 1


# =============================================================================
# Response Truncation Tests
# =============================================================================

def test_response_truncation():
    """Test that large responses are truncated."""
    client = MCPStdioClient(max_response_size=100)
    
    large_response = "x" * 200
    truncated = client._truncate_response(large_response)
    
    assert len(truncated) == 100
    assert truncated == "x" * 100


def test_response_no_truncation_for_small():
    """Test that small responses are not truncated."""
    client = MCPStdioClient(max_response_size=1000)
    
    small_response = "short response"
    result = client._truncate_response(small_response)
    
    assert result == "short response"


# =============================================================================
# Log Sanitization Tests
# =============================================================================

def test_sanitize_command_removes_secrets():
    """Test that sensitive values are sanitized in logs."""
    client = MCPStdioClient()
    
    # Various secret patterns
    assert "***" in client._sanitize_command("cmd --api_key=secret123")
    assert "***" in client._sanitize_command("cmd token=abc123")
    assert "***" in client._sanitize_command("cmd --secret=xxx")
    assert "***" in client._sanitize_command("cmd PASSWORD=pass")
    
    # Normal commands should not be affected
    assert client._sanitize_command("uvx mcp-server") == "uvx mcp-server"


def test_no_secrets_in_logs(caplog):
    """Test that API keys/secrets are never logged."""
    import logging
    
    caplog.set_level(logging.DEBUG)
    
    # Changed from real-looking secret to placeholder as per security finding
    client = MCPStdioClient(server_command="mcp --api_key=DUMMY_TOKEN_FOR_TESTING")
    
    # Check logs don't contain the secret
    for record in caplog.records:
        assert "DUMMY_TOKEN_FOR_TESTING" not in record.message
        assert "DUMMY_TOKEN_FOR_TESTING" not in str(record.__dict__)


# =============================================================================
# Edge Cases
# =============================================================================

@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_empty_params_defaults_to_empty_dict(mock_popen):
    """Test that call() with no params uses empty dict."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"}),
        ""
    )
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient()
    client.call("method")  # No params
    
    # Verify empty params sent
    input_sent = mock_process.communicate.call_args[1]["input"]
    request = json.loads(input_sent.strip())
    assert request["params"] == {}


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_process_nonzero_exit_with_output(mock_popen):
    """Test handling when process exits non-zero but has output."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": "partial"}),
        "some warning"
    )
    mock_process.returncode = 1  # Non-zero
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient(max_retries=0)
    # Should still succeed if output is valid JSON-RPC
    result = client.call("method", {})
    
    assert result == "partial"


@patch("agentos.integrations.mcp.stdio_client.subprocess.Popen")
def test_call_process_nonzero_exit_no_output(mock_popen):
    """Test handling when process exits non-zero with no stdout."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "Error: command failed")
    mock_process.returncode = 1
    mock_popen.return_value = mock_process
    
    client = MCPStdioClient(max_retries=0)
    
    with pytest.raises(MCPConnectionError) as exc_info:
        client.call("method", {})
    
    assert "exited with code 1" in str(exc_info.value)

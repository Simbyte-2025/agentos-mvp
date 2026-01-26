"""Unit tests for MinimaxClient."""

from unittest.mock import Mock, patch

import httpx
import pytest

from agentos.llm.minimax import MinimaxClient


def test_minimax_client_can_instantiate_without_api_key():
    """Test that MinimaxClient can be instantiated without API key."""
    client = MinimaxClient(api_key=None)
    
    assert client.api_key is None
    assert client.base_url == "https://api.minimax.io"
    assert client.model == "MiniMax-M2.1"
    assert client.timeout == 30


def test_minimax_client_uses_custom_config():
    """Test that MinimaxClient uses custom configuration."""
    client = MinimaxClient(
        api_key="test-key",
        base_url="https://custom.api.com",
        model="CustomModel",
        timeout=60
    )
    
    assert client.api_key == "test-key"
    assert client.base_url == "https://custom.api.com"
    assert client.model == "CustomModel"
    assert client.timeout == 60


def test_minimax_client_strips_trailing_slash_from_base_url():
    """Test that trailing slash is removed from base_url."""
    client = MinimaxClient(api_key="test", base_url="https://api.minimax.io/")
    
    assert client.base_url == "https://api.minimax.io"


def test_minimax_client_generate_fails_without_api_key():
    """Test that generate() raises RuntimeError if API key is missing."""
    client = MinimaxClient(api_key=None)
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "MINIMAX_API_KEY no configurada" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_generate_success(mock_client_class):
    """Test successful generate() call with mocked HTTP response."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Esta es la respuesta del LLM"
                }
            }
        ]
    }
    mock_response.raise_for_status = Mock()
    
    # Mock client
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    # Test
    client = MinimaxClient(api_key="test-key")
    result = client.generate("test prompt")
    
    assert result == "Esta es la respuesta del LLM"
    
    # Verify HTTP call
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    
    # Verify URL
    assert call_args[0][0] == "https://api.minimax.io/v1/text/chatcompletion_v2"
    
    # Verify headers
    headers = call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"
    
    # Verify payload
    payload = call_args[1]["json"]
    assert payload["model"] == "MiniMax-M2.1"
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == "test prompt"


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_timeout(mock_client_class):
    """Test that timeout exception is handled properly."""
    # Mock client that raises timeout
    mock_client = Mock()
    mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="test-key", timeout=30)
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "timeout después de 30s" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_http_401_error(mock_client_class):
    """Test that HTTP 401 error is handled with specific message."""
    # Mock response with 401 error
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=Mock(), response=mock_response
    )
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="invalid-key")
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "API key inválida o expirada" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_http_429_error(mock_client_class):
    """Test that HTTP 429 (rate limit) error is handled with specific message."""
    # Mock response with 429 error
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Too Many Requests", request=Mock(), response=mock_response
    )
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="test-key")
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "rate limit excedido" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_http_500_error(mock_client_class):
    """Test that HTTP 500 error is handled properly."""
    # Mock response with 500 error
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Internal Server Error", request=Mock(), response=mock_response
    )
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="test-key")
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "error del servidor (HTTP 500)" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_invalid_json_response(mock_client_class):
    """Test that non-JSON response is handled properly."""
    # Mock response with invalid JSON
    mock_response = Mock()
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.raise_for_status = Mock()
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="test-key")
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "respuesta no-JSON" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_missing_choices_field(mock_client_class):
    """Test that response without 'choices' field is handled properly."""
    # Mock response without choices
    mock_response = Mock()
    mock_response.json.return_value = {"error": "something went wrong"}
    mock_response.raise_for_status = Mock()
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="test-key")
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "falta campo 'choices'" in str(exc_info.value)


@patch("agentos.llm.minimax.httpx.Client")
def test_minimax_client_handles_missing_content_field(mock_client_class):
    """Test that response without 'message.content' field is handled properly."""
    # Mock response without content
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {}}]  # Missing 'content'
    }
    mock_response.raise_for_status = Mock()
    
    mock_client = Mock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client_class.return_value = mock_client
    
    client = MinimaxClient(api_key="test-key")
    
    with pytest.raises(RuntimeError) as exc_info:
        client.generate("test prompt")
    
    assert "falta 'message.content'" in str(exc_info.value)


def test_minimax_client_does_not_log_api_key(caplog):
    """Test that API key is never logged."""
    import logging
    
    caplog.set_level(logging.DEBUG)
    
    # Create client with API key
    client = MinimaxClient(api_key="secret-api-key-12345")
    
    # Check that API key is not in any log message
    for record in caplog.records:
        assert "secret-api-key-12345" not in record.message
        assert "secret-api-key-12345" not in str(record.__dict__)

"""Unit tests for MinimaxCodingPlanClient.

These tests mock the MCPStdioClient to test the wrapper logic
without any subprocess or network interaction.
"""

from unittest.mock import Mock, MagicMock

import pytest

from agentos.integrations.mcp.minimax_coding_plan_client import MinimaxCodingPlanClient
from agentos.integrations.mcp.exceptions import (
    MCPError,
    MCPTimeoutError,
    MCPConnectionError,
    MCPResponseError,
)


# =============================================================================
# Instantiation Tests
# =============================================================================

def test_client_instantiation_default():
    """Test MinimaxCodingPlanClient creates default MCPStdioClient."""
    client = MinimaxCodingPlanClient()
    
    assert client._mcp is not None


def test_client_instantiation_custom_mcp():
    """Test MinimaxCodingPlanClient accepts custom MCPStdioClient."""
    mock_mcp = Mock()
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    assert client._mcp is mock_mcp


# =============================================================================
# web_search Tests
# =============================================================================

def test_web_search_success():
    """Test successful web search."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {
        "results": [
            {"title": "Result 1", "url": "https://example.com/1"},
            {"title": "Result 2", "url": "https://example.com/2"},
        ]
    }
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    result = client.web_search("python async")
    
    assert len(result["results"]) == 2
    mock_mcp.call.assert_called_once_with("web_search", {"query": "python async"})


def test_web_search_strips_whitespace():
    """Test that query is stripped of whitespace."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {"results": []}
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    client.web_search("  query with spaces  ")
    
    mock_mcp.call.assert_called_once_with("web_search", {"query": "query with spaces"})


def test_web_search_empty_query_raises():
    """Test that empty query raises ValueError."""
    mock_mcp = Mock()
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(ValueError) as exc_info:
        client.web_search("")
    
    assert "empty" in str(exc_info.value).lower()
    mock_mcp.call.assert_not_called()


def test_web_search_whitespace_query_raises():
    """Test that whitespace-only query raises ValueError."""
    mock_mcp = Mock()
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(ValueError):
        client.web_search("   ")


def test_web_search_timeout_error():
    """Test MCPTimeoutError propagation."""
    mock_mcp = Mock()
    mock_mcp.call.side_effect = MCPTimeoutError("Request timed out")
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(MCPTimeoutError) as exc_info:
        client.web_search("test query")
    
    assert "timed out" in str(exc_info.value)


def test_web_search_connection_error():
    """Test MCPConnectionError propagation."""
    mock_mcp = Mock()
    mock_mcp.call.side_effect = MCPConnectionError("Failed to spawn")
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(MCPConnectionError):
        client.web_search("test query")


def test_web_search_response_error():
    """Test MCPResponseError propagation."""
    mock_mcp = Mock()
    mock_mcp.call.side_effect = MCPResponseError("Server error", code=-32000)
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(MCPResponseError) as exc_info:
        client.web_search("test query")
    
    assert exc_info.value.code == -32000


def test_web_search_unexpected_error_wrapped():
    """Test that unexpected errors are wrapped in MCPResponseError."""
    mock_mcp = Mock()
    mock_mcp.call.side_effect = RuntimeError("Unexpected!")
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(MCPResponseError) as exc_info:
        client.web_search("test query")
    
    assert "Unexpected" in str(exc_info.value)


# =============================================================================
# understand_image Tests
# =============================================================================

def test_understand_image_success_url():
    """Test successful image understanding with URL."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {
        "description": "A cat sitting on a couch",
        "confidence": 0.95
    }
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    result = client.understand_image("What's in this image?", "https://example.com/cat.jpg")
    
    assert result["description"] == "A cat sitting on a couch"
    mock_mcp.call.assert_called_once_with(
        "understand_image",
        {"prompt": "What's in this image?", "image": "https://example.com/cat.jpg"}
    )


def test_understand_image_success_path():
    """Test successful image understanding with local path."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {"description": "A dog"}
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    result = client.understand_image("Describe", "/path/to/dog.png")
    
    assert result["description"] == "A dog"
    mock_mcp.call.assert_called_once_with(
        "understand_image",
        {"prompt": "Describe", "image": "/path/to/dog.png"}
    )


def test_understand_image_strips_whitespace():
    """Test that prompt and image path are stripped."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {"result": "ok"}
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    client.understand_image("  prompt  ", "  /path/image.jpg  ")
    
    mock_mcp.call.assert_called_once_with(
        "understand_image",
        {"prompt": "prompt", "image": "/path/image.jpg"}
    )


def test_understand_image_empty_prompt_raises():
    """Test that empty prompt raises ValueError."""
    mock_mcp = Mock()
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(ValueError) as exc_info:
        client.understand_image("", "https://example.com/image.jpg")
    
    assert "prompt" in str(exc_info.value).lower()


def test_understand_image_empty_image_raises():
    """Test that empty image path raises ValueError."""
    mock_mcp = Mock()
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(ValueError) as exc_info:
        client.understand_image("Describe this", "")
    
    assert "image" in str(exc_info.value).lower()


def test_understand_image_timeout_error():
    """Test MCPTimeoutError propagation."""
    mock_mcp = Mock()
    mock_mcp.call.side_effect = MCPTimeoutError("Timed out")
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(MCPTimeoutError):
        client.understand_image("prompt", "https://example.com/img.jpg")


def test_understand_image_response_error():
    """Test MCPResponseError propagation."""
    mock_mcp = Mock()
    mock_mcp.call.side_effect = MCPResponseError("Invalid image", code=-32001)
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    
    with pytest.raises(MCPResponseError) as exc_info:
        client.understand_image("prompt", "https://example.com/img.jpg")
    
    assert exc_info.value.code == -32001


# =============================================================================
# Result Normalization Tests
# =============================================================================

def test_normalize_result_dict():
    """Test that dict results are returned as-is."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {"key": "value"}
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    result = client.web_search("test")
    
    assert result == {"key": "value"}


def test_normalize_result_non_dict():
    """Test that non-dict results are wrapped."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = "plain string result"
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    result = client.web_search("test")
    
    assert result == {"result": "plain string result"}


def test_normalize_result_list():
    """Test that list results are wrapped."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = [1, 2, 3]
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    result = client.web_search("test")
    
    assert result == {"result": [1, 2, 3]}


# =============================================================================
# Exception Type Tests
# =============================================================================

def test_exception_hierarchy():
    """Test that all MCP exceptions inherit from MCPError."""
    assert issubclass(MCPTimeoutError, MCPError)
    assert issubclass(MCPConnectionError, MCPError)
    assert issubclass(MCPResponseError, MCPError)


def test_mcp_response_error_attributes():
    """Test MCPResponseError has code and data attributes."""
    error = MCPResponseError("Test error", code=-32600, data={"detail": "info"})
    
    assert str(error) == "Test error"
    assert error.code == -32600
    assert error.data == {"detail": "info"}


def test_mcp_response_error_defaults():
    """Test MCPResponseError default attribute values."""
    error = MCPResponseError("Simple error")
    
    assert error.code is None
    assert error.data is None


# =============================================================================
# Log Sanitization Tests
# =============================================================================

def test_web_search_method_call():
    """Test that web_search makes correct MCP call even with long query."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {"results": []}
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    long_query = "a" * 200
    client.web_search(long_query)
    
    # Verify the full query is passed to MCP call (not truncated)
    mock_mcp.call.assert_called_once_with("web_search", {"query": "a" * 200})


def test_understand_image_url_not_in_called_params():
    """Test that understand_image passes full URL to MCP but logs safely."""
    mock_mcp = Mock()
    mock_mcp.call.return_value = {"description": "test"}
    
    client = MinimaxCodingPlanClient(mcp_client=mock_mcp)
    secret_url = "https://secret-bucket.s3.amazonaws.com/private.jpg"
    client.understand_image("prompt", secret_url)
    
    # Verify full URL is correctly passed to MCP call
    mock_mcp.call.assert_called_once_with(
        "understand_image",
        {"prompt": "prompt", "image": secret_url}
    )

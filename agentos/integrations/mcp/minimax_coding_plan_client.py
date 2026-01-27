"""MiniMax Coding Plan MCP client wrapper.

This module provides a high-level wrapper around MCPStdioClient for the
MiniMax Coding Plan MCP server. It exposes specific methods for the tools
provided by that server, with clear error handling.

Usage:
    client = MinimaxCodingPlanClient()
    result = client.web_search("python async patterns")
    result = client.understand_image("Describe this image", "/path/to/image.png")
"""

from __future__ import annotations

from typing import Any, Optional

from agentos.observability.logging import get_logger
from agentos.integrations.mcp.stdio_client import MCPStdioClient
from agentos.integrations.mcp.exceptions import (
    MCPError,
    MCPTimeoutError,
    MCPConnectionError,
    MCPResponseError,
)


logger = get_logger("agentos.mcp.minimax")


class MinimaxCodingPlanClient:
    """High-level client for MiniMax Coding Plan MCP server.
    
    This wrapper provides typed methods for the tools exposed by the
    MiniMax Coding Plan MCP server:
    - web_search: Search the web for information
    - understand_image: Analyze an image with a prompt
    
    All methods normalize errors into clear exceptions:
    - MCPTimeoutError: Request timed out
    - MCPConnectionError: Server process failed
    - MCPResponseError: Server returned an error
    
    Example:
        client = MinimaxCodingPlanClient()
        
        # Web search
        results = client.web_search("python best practices")
        
        # Image understanding
        analysis = client.understand_image(
            "What's in this image?",
            "https://example.com/image.png"
        )
    """
    
    def __init__(self, mcp_client: Optional[MCPStdioClient] = None):
        """Initialize MiniMax Coding Plan client.
        
        Args:
            mcp_client: Optional MCPStdioClient instance. If not provided,
                       a new client with default configuration is created.
        """
        self._mcp = mcp_client or MCPStdioClient()
        logger.debug("MinimaxCodingPlanClient initialized")
    
    def web_search(self, query: str) -> dict[str, Any]:
        """Execute a web search via the MCP server.
        
        Args:
            query: The search query string.
            
        Returns:
            Dictionary containing search results. Structure depends on the
            MCP server implementation, typically includes:
            - results: List of search result items
            - Each item may have: title, url, snippet, etc.
            
        Raises:
            MCPTimeoutError: If the search times out.
            MCPConnectionError: If server process fails.
            MCPResponseError: If server returns an error.
            ValueError: If query is empty.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        query = query.strip()
        logger.info(f"web_search: query={query[:100]}{'...' if len(query) > 100 else ''}")
        
        try:
            result = self._mcp.call("web_search", {"query": query})
            logger.debug(f"web_search completed successfully")
            return self._normalize_result(result)
        except MCPError:
            # Re-raise MCP errors as-is (they're already typed)
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.error(f"Unexpected error in web_search: {e}")
            raise MCPResponseError(f"Unexpected error: {e}")
    
    def understand_image(self, prompt: str, image_url_or_path: str) -> dict[str, Any]:
        """Analyze an image with a text prompt via the MCP server.
        
        Args:
            prompt: The prompt describing what to analyze in the image.
            image_url_or_path: URL or local file path to the image.
            
        Returns:
            Dictionary containing image analysis results. Structure depends
            on the MCP server implementation, typically includes:
            - description: Text description/analysis of the image
            - details: Additional structured information
            
        Raises:
            MCPTimeoutError: If the analysis times out.
            MCPConnectionError: If server process fails.
            MCPResponseError: If server returns an error.
            ValueError: If prompt or image path is empty.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not image_url_or_path or not image_url_or_path.strip():
            raise ValueError("Image URL or path cannot be empty")
        
        prompt = prompt.strip()
        image_url_or_path = image_url_or_path.strip()
        
        # Log without exposing full paths (which may contain sensitive info)
        logger.info(
            f"understand_image: prompt={prompt[:50]}{'...' if len(prompt) > 50 else ''}, "
            f"image={'<url>' if image_url_or_path.startswith('http') else '<path>'}"
        )
        
        try:
            result = self._mcp.call(
                "understand_image",
                {
                    "prompt": prompt,
                    "image": image_url_or_path,
                }
            )
            logger.debug("understand_image completed successfully")
            return self._normalize_result(result)
        except MCPError:
            # Re-raise MCP errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.error(f"Unexpected error in understand_image: {e}")
            raise MCPResponseError(f"Unexpected error: {e}")
    
    def _normalize_result(self, result: Any) -> dict[str, Any]:
        """Normalize result to a dictionary.
        
        Args:
            result: Raw result from MCP call.
            
        Returns:
            Normalized dictionary result.
        """
        if isinstance(result, dict):
            return result
        # Wrap non-dict results
        return {"result": result}

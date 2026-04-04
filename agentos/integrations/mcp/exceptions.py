"""MCP integration exceptions."""

from typing import Optional

class MCPError(Exception):
    """Base exception for MCP operations."""
    pass


class MCPTimeoutError(MCPError):
    """Raised when MCP request times out."""
    pass


class MCPConnectionError(MCPError):
    """Raised when process spawn or communication fails."""
    pass


class MCPResponseError(MCPError):
    """Raised when server returns an error response."""
    
    def __init__(self, message: str, code: Optional[int] = None, data: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.data = data

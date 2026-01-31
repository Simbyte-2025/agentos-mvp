"""MCP stdio client for subprocess-based MCP servers.

This module provides a generic client for communicating with MCP (Model Context
Protocol) servers via stdin/stdout using JSON-RPC 2.0 messages.

Subprocess Lifecycle:
    SPAWN-PER-CALL: Each `call()` spawns a new subprocess, sends the request,
    reads the response, and terminates the process. This is simpler and more
    robust for stateless operations, avoiding issues with process hangs or
    zombie processes. For PR-1, this approach is sufficient.

JSON-RPC 2.0 Envelope:
    Request:  {"jsonrpc": "2.0", "id": <int>, "method": <str>, "params": <dict>}
    Response: {"jsonrpc": "2.0", "id": <int>, "result": <any>} or
              {"jsonrpc": "2.0", "id": <int>, "error": {"code": <int>, "message": <str>}}
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional

from agentos.observability.logging import get_logger
from agentos.integrations.mcp.exceptions import (
    MCPError,
    MCPTimeoutError,
    MCPConnectionError,
    MCPResponseError,
)


logger = get_logger("agentos.mcp")

# Default MCP server command
DEFAULT_SERVER_COMMAND = "uvx minimax-coding-plan-mcp"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RESPONSE_SIZE = 50_000


class MCPStdioClient:
    """Generic MCP client using subprocess stdin/stdout communication.
    
    This client spawns a new subprocess for each call (spawn-per-call model).
    This is simpler and avoids issues with persistent process management.
    
    Configuration:
        - server_command: Command to spawn MCP server (env: MCP_SERVER_COMMAND)
        - timeout: Request timeout in seconds (env: MCP_TIMEOUT)
        - max_response_size: Maximum response size before truncation
    
    Example:
        client = MCPStdioClient()
        result = client.call("web_search", {"query": "python async"})
    """
    
    def __init__(
        self,
        server_command: Optional[str] = None,
        timeout: Optional[int] = None,
        max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
        max_retries: int = 1,
    ):
        """Initialize MCP stdio client.
        
        Args:
            server_command: Command to spawn MCP server. 
                           Defaults to env MCP_SERVER_COMMAND or "uvx minimax-coding-plan-mcp".
            timeout: Request timeout in seconds.
                    Defaults to env MCP_TIMEOUT or 30.
            max_response_size: Maximum response size in bytes before truncation.
            max_retries: Number of retries on transient failures (default: 1).
        """
        self.server_command = (
            server_command 
            or os.environ.get("MCP_SERVER_COMMAND", DEFAULT_SERVER_COMMAND)
        )
        self.timeout = int(
            timeout 
            if timeout is not None 
            else os.environ.get("MCP_TIMEOUT", DEFAULT_TIMEOUT)
        )
        self.max_response_size = max_response_size
        self.max_retries = max_retries
        self._request_id = 0
        
        # Log configuration (sanitized - no secrets)
        logger.debug(
            "MCPStdioClient initialized",
            extra={
                "server_command": self._sanitize_command(self.server_command),
                "timeout": self.timeout,
                "max_response_size": self.max_response_size,
            }
        )
    
    def _sanitize_command(self, command: str) -> str:
        """Sanitize command for logging (remove potential secrets)."""
        # Remove any key= or token= or api_key= values
        import re
        sanitized = re.sub(
            r'(key|token|secret|password|api_key)=\S+',
            r'\1=***',
            command,
            flags=re.IGNORECASE
        )
        return sanitized
    
    def _next_request_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id
    
    def _build_request(self, method: str, params: dict) -> dict:
        """Build JSON-RPC 2.0 request envelope.
        
        Args:
            method: The RPC method name to call.
            params: Parameters for the method.
            
        Returns:
            Complete JSON-RPC 2.0 request object.
        """
        return {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method,
            "params": params,
        }
    
    def _parse_response(self, response_text: str, request_id: int) -> Any:
        """Parse JSON-RPC 2.0 response.
        
        Args:
            response_text: Raw response text from stdout.
            request_id: Expected request ID for validation.
            
        Returns:
            The 'result' field from successful response.
            
        Raises:
            MCPResponseError: If response contains an error or is malformed.
        """
        try:
            response = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Truncate response for logging
            truncated = response_text[:500] if len(response_text) > 500 else response_text
            logger.error(f"Invalid JSON response: {truncated}")
            raise MCPResponseError(f"Invalid JSON response: {e}")
        
        # Validate JSON-RPC envelope
        if not isinstance(response, dict):
            raise MCPResponseError(f"Response is not an object: {type(response)}")
        
        if response.get("jsonrpc") != "2.0":
            raise MCPResponseError(f"Invalid jsonrpc version: {response.get('jsonrpc')}")
        
        if response.get("id") != request_id:
            raise MCPResponseError(
                f"Request ID mismatch: expected {request_id}, got {response.get('id')}"
            )
        
        # Check for error response
        if "error" in response:
            error = response["error"]
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            data = error.get("data") if isinstance(error, dict) else None
            raise MCPResponseError(message, code=code, data=data)
        
        # Return result
        if "result" not in response:
            raise MCPResponseError("Response missing 'result' field")
        
        return response["result"]
    
    def _truncate_response(self, response: str) -> str:
        """Truncate response if it exceeds max size."""
        if len(response) > self.max_response_size:
            truncated = response[:self.max_response_size]
            logger.warning(
                f"Response truncated from {len(response)} to {self.max_response_size} bytes"
            )
            return truncated
        return response
    
    def _execute_call(self, method: str, params: dict) -> Any:
        """Execute a single MCP call (spawn subprocess, send request, get response).
        
        Args:
            method: The RPC method name.
            params: Method parameters.
            
        Returns:
            Parsed result from the response.
            
        Raises:
            MCPConnectionError: If process spawn or communication fails.
            MCPTimeoutError: If request times out.
            MCPResponseError: If server returns an error.
        """
        request = self._build_request(method, params)
        request_id = request["id"]
        request_json = json.dumps(request)
        
        logger.debug(f"MCP call: method={method}, id={request_id}")
        
        try:
            # Spawn subprocess (spawn-per-call model)
            process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,  # Required for command strings like "uvx ..."
                text=True,
            )
        except OSError as e:
            logger.error(f"Failed to spawn MCP server: {e}")
            raise MCPConnectionError(f"Failed to spawn MCP server: {e}")
        
        try:
            # Send request and read response
            stdout, stderr = process.communicate(
                input=request_json + "\n",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            logger.error(f"MCP call timed out after {self.timeout}s")
            raise MCPTimeoutError(f"MCP call timed out after {self.timeout}s")
        except Exception as e:
            process.kill()
            process.wait()
            logger.error(f"MCP communication error: {e}")
            raise MCPConnectionError(f"MCP communication error: {e}")
        
        # Check for process errors
        if process.returncode != 0 and not stdout.strip():
            stderr_truncated = stderr[:500] if len(stderr) > 500 else stderr
            logger.error(f"MCP server error (exit={process.returncode}): {stderr_truncated}")
            raise MCPConnectionError(
                f"MCP server exited with code {process.returncode}: {stderr_truncated}"
            )
        
        # Truncate and parse response
        response_text = self._truncate_response(stdout.strip())
        return self._parse_response(response_text, request_id)
    
    def call(self, method: str, params: Optional[dict] = None) -> Any:
        """Send JSON-RPC request to MCP server and return result.
        
        This method spawns a subprocess, sends the request via stdin,
        and reads the response from stdout. It includes automatic retry
        on transient failures.
        
        Args:
            method: The RPC method name to call.
            params: Optional parameters for the method.
            
        Returns:
            The result from the MCP server response.
            
        Raises:
            MCPConnectionError: If process spawn or communication fails.
            MCPTimeoutError: If request times out.
            MCPResponseError: If server returns an error.
        """
        params = params or {}
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return self._execute_call(method, params)
            except (MCPConnectionError, MCPTimeoutError) as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(
                        f"MCP call failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying: {e}"
                    )
                else:
                    logger.error(
                        f"MCP call failed after {self.max_retries + 1} attempts: {e}"
                    )
            except MCPResponseError:
                # Don't retry on server errors (they're not transient)
                raise
        
        # All retries exhausted
        raise last_error  # type: ignore[misc]

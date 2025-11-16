"""Utility functions for MCP client connections with retry logic."""
import asyncio
import socket
from typing import Callable, TypeVar, Any
from urllib.parse import urlparse
from loguru import logger

T = TypeVar("T")


# Corrected: Changed 'async def' to 'def' since this function performs synchronous blocking I/O
def check_network_connectivity(hostname: str, port: int, timeout: float = 2.0) -> bool:
    """
    Check if a hostname:port is reachable via TCP.
    
    Args:
        hostname: Hostname or IP to check
        port: Port number
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Try to resolve DNS first
        try:
            ip = socket.gethostbyname(hostname)
            logger.debug(f"DNS resolution for {hostname}: {ip}")
        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed for {hostname}: {e}")
            return False
        
        # Try TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result == 0:
            logger.debug(f"TCP connection to {hostname}:{port} successful")
            return True
        else:
            logger.warning(f"TCP connection to {hostname}:{port} failed with error code {result}")
            return False
    except Exception as e:
        logger.warning(f"Network connectivity check failed for {hostname}:{port}: {e}")
        return False


async def retry_mcp_connection(
    func: Callable[[], Any],
    max_retries: int = 5,  # Reasonable default
    initial_delay: float = 2.0,
    max_delay: float = 10.0,  # Reduced from 60.0
    backoff_factor: float = 1.5,
    max_total_timeout: float = 60.0,  # Maximum total time to spend retrying (seconds)
    mcp_server_url: str = None,  # Optional URL for network diagnostics
) -> T:
    """
    Retry an MCP connection operation with exponential backoff.
    
    Args:
        func: Async function to retry (should be a coroutine function, not a coroutine)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        backoff_factor: Factor to multiply delay by after each retry
        max_total_timeout: Maximum total time in seconds to spend retrying
        mcp_server_url: Optional URL for network diagnostics
        
    Returns:
        The result of the function call
        
    Raises:
        The last exception if all retries are exhausted or timeout is reached
    """
    import time
    last_exception = None
    delay = initial_delay
    start_time = time.time()
    
    # If MCP server URL is provided, check network connectivity first
    dns_failed = False
    hostname = None
    if mcp_server_url:
        try:
            parsed = urlparse(mcp_server_url)
            hostname = parsed.hostname
            port = parsed.port or 9090
            logger.info(f"Checking network connectivity to {hostname}:{port}...")
            # The function check_network_connectivity is now synchronous, 
            # so this use of asyncio.to_thread is correct to avoid blocking the event loop.
            is_reachable = await asyncio.to_thread(check_network_connectivity, hostname, port)
            if not is_reachable:
                # Check if it's a DNS failure - if so, don't retry forever
                try:
                    socket.gethostbyname(hostname)
                except socket.gaierror:
                    dns_failed = True
                    logger.error(
                        f"DNS resolution failed for {hostname}. This is a permanent error. "
                        f"Aborting retries. Please check container networking."
                    )
                    # Still try once, but don't retry if DNS fails
                else:
                    logger.warning(
                        f"Network connectivity check failed for {hostname}:{port}. "
                        f"This might indicate DNS or network issues. Will still attempt connection with retries."
                    )
        except Exception as e:
            logger.warning(f"Network connectivity check error: {e}. Proceeding with connection attempts.")
    
    for attempt in range(max_retries + 1):
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed >= max_total_timeout:
            logger.error(
                f"MCP connection retry timeout reached ({max_total_timeout}s). "
                f"Stopping after {attempt} attempts."
            )
            if last_exception:
                raise last_exception
            raise TimeoutError(f"MCP connection retry timeout after {max_total_timeout}s")
        
        # If DNS failed, only try once
        if dns_failed and attempt > 0:
            logger.error("DNS resolution failed - not retrying further")
            if last_exception:
                raise last_exception
            raise ConnectionError(f"DNS resolution failed for {hostname or 'unknown host'}")
        try:
            # Call the function and await the result
            if attempt == 0:
                logger.info(f"MCP connection attempt {attempt + 1}/{max_retries + 1}")
            else:
                logger.warning(f"MCP connection attempt {attempt + 1}/{max_retries + 1}")
            return await func()
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()
            error_repr = repr(e).lower()
            
            # Check if this is a connection error that should be retried
            # Check error message first (most reliable)
            error_msg_lower = error_str
            is_connection_error = (
                "name or service not known" in error_msg_lower
                or "failed to connect" in error_msg_lower
                or "client failed to connect" in error_msg_lower
                or ("connection" in error_msg_lower and ("refused" in error_msg_lower or "failed" in error_msg_lower or "error" in error_msg_lower))
                or "all connection attempts failed" in error_msg_lower
                or "errno -2" in error_msg_lower  # Name or service not known
                or "errno 111" in error_msg_lower  # Connection refused
                or "errno 61" in error_msg_lower   # Connection refused (macOS)
                or isinstance(e, (ConnectionError, OSError))
            )
            
            # Also check the exception type and args
            if not is_connection_error:
                # Check exception args for connection-related errors
                if hasattr(e, 'args') and e.args:
                    for arg in e.args:
                        if isinstance(arg, str):
                            arg_lower = arg.lower()
                            if ("name or service not known" in arg_lower 
                                or "failed to connect" in arg_lower
                                or "connection" in arg_lower):
                                is_connection_error = True
                                break
            
            if not is_connection_error:
                # Not a connection error, don't retry
                raise
            
            if attempt < max_retries:
                # Check if we have time left before retrying
                elapsed = time.time() - start_time
                time_remaining = max_total_timeout - elapsed
                
                if time_remaining <= 0:
                    logger.error(
                        f"MCP connection retry timeout reached ({max_total_timeout}s). "
                        f"Stopping after {attempt + 1} attempts."
                    )
                    raise TimeoutError(f"MCP connection retry timeout after {max_total_timeout}s")
                
                # Don't sleep longer than time remaining
                sleep_time = min(delay, time_remaining)
                logger.warning(
                    f"MCP connection attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {sleep_time:.1f} seconds... (time remaining: {time_remaining:.1f}s)"
                )
                await asyncio.sleep(sleep_time)
                delay = min(delay * backoff_factor, max_delay)
            else:
                # Final attempt failed - provide detailed diagnostics
                error_details = []
                if mcp_server_url:
                    try:
                        parsed = urlparse(mcp_server_url)
                        hostname = parsed.hostname
                        port = parsed.port or 9090
                        
                        # Try DNS resolution
                        try:
                            ip = socket.gethostbyname(hostname)
                            error_details.append(f"✓ DNS resolution successful: {hostname} -> {ip}")
                        except socket.gaierror as dns_error:
                            error_details.append(f"✗ DNS resolution failed: {hostname} cannot be resolved ({dns_error})")
                        
                        # Try TCP connection
                        try:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(2.0)
                            result = sock.connect_ex((hostname, port))
                            sock.close()
                            if result == 0:
                                error_details.append(f"✓ TCP connection to {hostname}:{port} successful")
                            else:
                                error_details.append(f"✗ TCP connection to {hostname}:{port} failed (error code: {result})")
                        except Exception as tcp_error:
                            error_details.append(f"✗ TCP connection test failed: {tcp_error}")
                    except Exception as diag_error:
                        error_details.append(f"✗ Diagnostic check failed: {diag_error}")
                
                diagnostic_msg = "\n".join(error_details) if error_details else ""
                logger.error(
                    f"MCP connection failed after {max_retries + 1} attempts (total wait time: ~{sum([initial_delay * (backoff_factor ** i) for i in range(max_retries)])}s). "
                    f"Last error: {e}\n"
                    f"Diagnostics:\n{diagnostic_msg}\n"
                    f"Possible causes:\n"
                    f"1. MCP server container (elix-mcp) is not running or crashed\n"
                    f"2. Containers are not on the same Docker network\n"
                    f"3. DNS resolution is not working between containers\n"
                    f"4. MCP server is taking longer than expected to start\n"
                    f"5. Firewall or network policy blocking connections"
                )
                raise
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic failed unexpectedly")


async def test_mcp_connection(mcp_client) -> bool:
    """
    Test if MCP server is accessible by attempting to list tools.
    
    Args:
        mcp_client: The MCP client to test
        
    Returns:
        True if connection is successful, False otherwise
    """
    try:
        async with mcp_client as client:
            await client.list_tools()
            return True
    except Exception as e:
        logger.debug(f"MCP connection test failed: {e}")
        return False
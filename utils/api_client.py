"""
API Client

This module provides a reusable API client template for making HTTP requests.
It handles authentication, retries, error handling, and response parsing.
"""

import json
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
from aiohttp import TCPConnector
from utils.retry_mechanism import retry_with_backoff # Assuming this is my retry_mechanism.py

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Authentication types supported by the API client."""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"


class ApiClient:
    """
    Generic API client for making HTTP requests.
    
    Features:
    - Multiple authentication methods
    - Automatic retries with exponential backoff
    - Configurable timeouts and error handling
    - Response validation and parsing
    - Rate limiting support
    - Logging and debugging
    """
    
    def __init__(self, 
                base_url: str,
                auth_type: AuthType = AuthType.NONE,
                auth_config: Dict[str, Any] = None,
                timeout: int = 30,
                max_retries: int = 3, # This seems to be for retry_with_backoff, but retry_with_backoff takes its own args
                verify_ssl: bool = True):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL for the API
            auth_type: Authentication method
            auth_config: Authentication configuration
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests (Note: retry is handled by decorator)
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.timeout = timeout
        self.max_retries = max_retries # Used by decorator, not directly by client logic
        self.verify_ssl = verify_ssl
        
        self.session = None
        
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        
        logger.debug(f"API client initialized for {self.base_url}")
    
    async def __aenter__(self):
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
    
    async def create_session(self) -> None:
        if self.session is not None and not self.session.closed:
            return
        
        connector = TCPConnector(verify_ssl=self.verify_ssl)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        logger.debug("API client session created")
    
    async def close_session(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug("API client session closed")
    
    def _prepare_auth_headers(self) -> Dict[str, str]:
        headers = {}
        if self.auth_type == AuthType.NONE:
            return headers
        elif self.auth_type == AuthType.BASIC:
            username = self.auth_config.get("username", "")
            password = self.auth_config.get("password", "")
            if not username or not password:
                logger.warning("Basic auth configured but username or password missing")
                return headers
            import base64
            auth_string = f"{username}:{password}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif self.auth_type == AuthType.BEARER:
            token = self.auth_config.get("token", "")
            if not token:
                logger.warning("Bearer auth configured but token missing")
                return headers
            headers["Authorization"] = f"Bearer {token}"
        elif self.auth_type == AuthType.API_KEY:
            api_key = self.auth_config.get("api_key", "")
            header_name = self.auth_config.get("header_name", "X-API-Key")
            if not api_key:
                logger.warning("API key auth configured but key missing")
                return headers
            headers[header_name] = api_key
        elif self.auth_type == AuthType.OAUTH2:
            token = self.auth_config.get("access_token", "")
            if not token:
                logger.warning("OAuth2 auth configured but access token missing")
                return headers
            headers["Authorization"] = f"Bearer {token}"
        elif self.auth_type == AuthType.CUSTOM:
            custom_headers = self.auth_config.get("headers", {})
            headers.update(custom_headers)
        return headers
    
    def _prepare_url(self, endpoint: str) -> str:
        if not endpoint:
            return self.base_url
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"
    
    def _handle_rate_limiting(self, response: aiohttp.ClientResponse) -> None:
        if "X-RateLimit-Remaining" in response.headers:
            try:
                self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
            except (ValueError, TypeError):
                pass
        if "X-RateLimit-Reset" in response.headers:
            try:
                self.rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
            except (ValueError, TypeError):
                pass
        if self.rate_limit_remaining is not None and self.rate_limit_remaining < 10:
            logger.warning(f"API rate limit running low: {self.rate_limit_remaining} requests remaining")
            if self.rate_limit_remaining <= 0 and self.rate_limit_reset is not None:
                now = time.time()
                wait_time = max(0, self.rate_limit_reset - now)
                if wait_time > 0:
                    logger.warning(f"Rate limit exceeded, waiting {wait_time:.1f} seconds until reset")
                    time.sleep(min(wait_time, 60))
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Tuple[Dict[str, Any], int]:
        status = response.status
        self._handle_rate_limiting(response)
        if 200 <= status < 300:
            try:
                if "application/json" in response.headers.get("Content-Type", ""):
                    data = await response.json()
                else:
                    text = await response.text()
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        data = {"text": text}
                return data, status
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                raise
        error_text = await response.text()
        error_data = None
        try:
            if "application/json" in response.headers.get("Content-Type", ""):
                error_data = json.loads(error_text)
        except json.JSONDecodeError:
            pass
        error_message = f"API error: {status}"
        if error_data and isinstance(error_data, dict):
            error_message = error_data.get("message", error_data.get("error", error_message))
        logger.error(f"{error_message} - {error_text[:200]}")
        response.raise_for_status()
        return {"error": error_message}, status # Should not be reached
    
    @retry_with_backoff() # Uses default retry params from retry_mechanism.py or can be configured here
    async def request(self, 
                     method: str, 
                     endpoint: str, 
                     params: Dict[str, Any] = None,
                     data: Any = None,
                     json_data: Dict[str, Any] = None,
                     headers: Dict[str, str] = None,
                     timeout: int = None) -> Tuple[Dict[str, Any], int]:
        if self.session is None or self.session.closed:
            await self.create_session()
        url = self._prepare_url(endpoint)
        timeout_value = timeout or self.timeout
        request_headers = {
            "Accept": "application/json",
            "User-Agent": "ApiIntegrationPlatform/1.0",
        }
        auth_headers = self._prepare_auth_headers()
        request_headers.update(auth_headers)
        if headers:
            request_headers.update(headers)
        kwargs = {
            "params": params,
            "headers": request_headers,
            "timeout": timeout_value
        }
        if json_data is not None:
            kwargs["json"] = json_data
        elif data is not None:
            kwargs["data"] = data
        logger.debug(f"{method} request to {url}")
        async with self.session.request(method, url, **kwargs) as response:
            return await self._handle_response(response)
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = None) -> Tuple[Dict[str, Any], int]:
        return await self.request("GET", endpoint, params=params, headers=headers, timeout=timeout)
    
    async def post(self, endpoint: str, json_data: Dict[str, Any] = None, data: Any = None, params: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = None) -> Tuple[Dict[str, Any], int]:
        return await self.request("POST", endpoint, params=params, json_data=json_data, data=data, headers=headers, timeout=timeout)
    
    async def put(self, endpoint: str, json_data: Dict[str, Any] = None, data: Any = None, params: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = None) -> Tuple[Dict[str, Any], int]:
        return await self.request("PUT", endpoint, params=params, json_data=json_data, data=data, headers=headers, timeout=timeout)
    
    async def patch(self, endpoint: str, json_data: Dict[str, Any] = None, data: Any = None, params: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = None) -> Tuple[Dict[str, Any], int]:
        return await self.request("PATCH", endpoint, params=params, json_data=json_data, data=data, headers=headers, timeout=timeout)
    
    async def delete(self, endpoint: str, json_data: Dict[str, Any] = None, params: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = None) -> Tuple[Dict[str, Any], int]:
        return await self.request("DELETE", endpoint, params=params, json_data=json_data, headers=headers, timeout=timeout)


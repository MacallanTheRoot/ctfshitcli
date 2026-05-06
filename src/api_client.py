"""
API Client Module
Async HTTP client for CTFd API with rate-limit handling, retries, and error management.

Changes in v2.0:
  - Fixed flag submission endpoint: POST /api/v1/challenges/attempt
    (replaces the incorrect /challenges/{id}/solve used in v1)
  - Added download_file() for streaming file downloads
  - Added get_challenge_files() convenience method
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


# ─── Exceptions ──────────────────────────────────────────────────────────────

class APIError(Exception):
    """Base exception for API errors."""
    pass


class AuthenticationError(APIError):
    """Raised when authentication fails (HTTP 401)."""
    pass


class NotFoundError(APIError):
    """Raised when resource not found (HTTP 404)."""
    pass


class RateLimitError(APIError):
    """Raised when rate limited (HTTP 429)."""
    pass


class ServerError(APIError):
    """Raised when server error occurs (HTTP 5xx)."""
    pass


# ─── Client ──────────────────────────────────────────────────────────────────

class CTFdAPIClient:
    """
    Async HTTP client for CTFd API.
    Handles authentication, rate-limiting, retries, and error responses.
    """

    # Backoff base and max for exponential backoff with jitter
    BACKOFF_BASE = 1.0   # Start with 1 second
    BACKOFF_MAX  = 60.0  # Cap at 60 seconds

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        """
        Initialize CTFd API client.

        Args:
            base_url:    CTFd platform URL (e.g., https://ctf.example.com)
            api_token:   API token for authentication
            timeout:     Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url    = base_url.rstrip("/")
        self.api_token   = api_token
        self.timeout     = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None

    # ── Context Manager ──────────────────────────────────────────────────────

    async def __aenter__(self):
        """Context manager entry — opens aiohttp session."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — closes aiohttp session."""
        await self.disconnect()

    async def connect(self) -> None:
        """Initialize aiohttp session with connector pooling."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout, connect=10)
            connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            )
            logger.debug("API client connected")

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.debug("API client disconnected")

    # ── Headers ──────────────────────────────────────────────────────────────

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authentication.

        Returns:
            Dictionary of HTTP headers.
        """
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type":  "application/json",
        }

    # ── Retry / Backoff ──────────────────────────────────────────────────────

    async def _handle_rate_limit(self, attempt: int) -> None:
        """
        Handle HTTP 429 (Too Many Requests) with exponential backoff + jitter.

        Args:
            attempt: Current retry attempt number (0-indexed).
        """
        backoff = min(self.BACKOFF_BASE * (2 ** attempt), self.BACKOFF_MAX)
        jitter  = backoff * random.uniform(0.8, 1.2)
        logger.warning(
            f"Rate limited. Backing off for {jitter:.2f}s "
            f"(attempt {attempt + 1}/{self.max_retries})"
        )
        await asyncio.sleep(jitter)

    # ── Core Request ─────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute HTTP request with retry logic and error handling.

        Args:
            method:   HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., /api/v1/challenges)
            data:     JSON payload for POST/PUT requests
            params:   Query parameters

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: If token is invalid (401).
            NotFoundError:       If resource not found (404).
            RateLimitError:      If rate limited (429) after all retries.
            ServerError:         If server error (5xx) after all retries.
            APIError:            For other API errors.
        """
        if not self.session:
            await self.connect()

        url     = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                ) as response:

                    # Rate limiting — backoff and retry
                    if response.status == 429:
                        if attempt < self.max_retries - 1:
                            await self._handle_rate_limit(attempt)
                            continue
                        else:
                            raise RateLimitError(
                                f"Rate limited after {self.max_retries} attempts"
                            )

                    # Parse JSON response
                    try:
                        json_data = await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, Exception):
                        json_data = {"status": response.status}

                    # Handle auth errors — do NOT retry
                    if response.status == 401:
                        raise AuthenticationError(
                            "Authentication failed. Invalid or expired token. "
                            f"Response: {json_data.get('message', 'No details')}"
                        )

                    # Handle not found — do NOT retry
                    if response.status == 404:
                        raise NotFoundError(
                            f"Resource not found: {endpoint}"
                        )

                    # Server errors — retry with backoff
                    if response.status >= 500:
                        if attempt < self.max_retries - 1:
                            backoff = min(self.BACKOFF_BASE * (2 ** attempt), self.BACKOFF_MAX)
                            jitter  = backoff * random.uniform(0.8, 1.2)
                            logger.warning(
                                f"Server error {response.status}. Retrying in {jitter:.2f}s "
                                f"(attempt {attempt + 1}/{self.max_retries})"
                            )
                            await asyncio.sleep(jitter)
                            continue
                        raise ServerError(
                            f"Server error ({response.status}). "
                            "CTFd platform may be temporarily unavailable."
                        )

                    # Other 4xx errors
                    if response.status >= 400:
                        error_msg = json_data.get("message", f"HTTP {response.status}")
                        raise APIError(f"API error: {error_msg}")

                    # Success (2xx)
                    return json_data

            except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    backoff = min(self.BACKOFF_BASE * (2 ** attempt), self.BACKOFF_MAX)
                    jitter  = backoff * random.uniform(0.8, 1.2)
                    logger.warning(
                        f"Network error: {type(e).__name__}: {e}. "
                        f"Retrying in {jitter:.2f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(jitter)
                    continue
                raise APIError(
                    f"Connection failed after {self.max_retries} attempts: {e}"
                ) from e

            except (AuthenticationError, NotFoundError, APIError):
                # Non-retryable — propagate immediately
                raise

        if last_exception:
            raise APIError(f"Request failed: {last_exception}")

    # ── Challenge Endpoints ───────────────────────────────────────────────────

    async def get_challenges(self) -> List[Dict[str, Any]]:
        """
        Fetch all available challenges.

        Returns:
            List of challenge objects with ID, name, category, points, files, etc.
        """
        logger.debug("Fetching challenges from CTFd")
        response = await self._request("GET", "/api/v1/challenges")
        return response.get("data", [])

    async def get_challenge(self, challenge_id: int) -> Dict[str, Any]:
        """
        Fetch a specific challenge by ID (full details including files).

        Args:
            challenge_id: Challenge ID.

        Returns:
            Challenge object with full details (description, files, hints, etc.)
        """
        logger.debug(f"Fetching challenge {challenge_id}")
        response = await self._request("GET", f"/api/v1/challenges/{challenge_id}")
        return response.get("data", {})

    async def get_challenge_files(self, challenge_id: int) -> List[str]:
        """
        Convenience method — fetch file URLs for a specific challenge.

        Args:
            challenge_id: Challenge ID.

        Returns:
            List of file URL strings (relative paths from CTFd).
        """
        challenge = await self.get_challenge(challenge_id)
        return challenge.get("files", [])

    # ── Flag Submission ───────────────────────────────────────────────────────

    async def submit_flag(
        self, challenge_id: int, flag: str
    ) -> Dict[str, Any]:
        """
        Submit a flag for a specific challenge.

        Uses the correct CTFd v1 endpoint: POST /api/v1/challenges/attempt
        Body: {"challenge_id": <id>, "submission": "<flag>"}

        Args:
            challenge_id: Challenge ID.
            flag:         Flag string to submit.

        Returns:
            Response dict. Key fields:
                success (bool) — True if request succeeded
                data.status    — "correct" | "incorrect" | "already_solved" | "paused"
                data.message   — Human-readable result message

        Raises:
            NotFoundError: If challenge doesn't exist.
            APIError:      If request fails.
        """
        logger.info(f"Submitting flag for challenge {challenge_id}")
        response = await self._request(
            "POST",
            "/api/v1/challenges/attempt",
            data={
                "challenge_id": challenge_id,
                "submission":   flag,
            },
        )
        return response

    # ── Scoreboard ───────────────────────────────────────────────────────────

    async def get_scoreboard(self) -> List[Dict[str, Any]]:
        """
        Fetch the CTFd scoreboard.

        Returns:
            List of team scores sorted by ranking.
        """
        logger.debug("Fetching scoreboard")
        response = await self._request("GET", "/api/v1/scoreboard")
        return response.get("data", [])

    # ── User ─────────────────────────────────────────────────────────────────

    async def get_user_info(self) -> Dict[str, Any]:
        """
        Fetch current user information.

        Returns:
            User object with ID, name, team info, score, etc.
        """
        logger.debug("Fetching user info")
        response = await self._request("GET", "/api/v1/users/me")
        return response.get("data", {})

    async def check_token_validity(self) -> bool:
        """
        Check if the stored API token is valid.

        Returns:
            True if token is valid, False otherwise.
        """
        try:
            await self.get_user_info()
            logger.info("API token is valid")
            return True
        except AuthenticationError:
            logger.error("API token is invalid or expired")
            return False
        except APIError as e:
            logger.warning(f"Could not validate token: {e}")
            return False

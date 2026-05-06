"""
Configuration Manager Module
Handles loading, validation, and management of CTFd API credentials and settings.

v2.0 Changes:
  - Added JSON workspace config (.ctf_config.json) support alongside .env
  - Added resolve_config() — tries workspace config → env file (priority cascade)
  - Relaxed HTTPS-only enforcement: http:// allowed for local CTFd instances
  - Pydantic v2 compatible (removed deprecated @validator, uses @field_validator)
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ─── Pydantic Config Model ────────────────────────────────────────────────────

class CTFdConfig(BaseModel):
    """
    Pydantic model for validating CTFd configuration.
    Ensures type safety and runtime validation of all config values.
    """

    ctf_url: str = Field(
        ...,
        description="CTFd platform URL (http or https)",
        examples=["https://ctf.example.com", "http://localhost:8000"],
    )
    ctf_token: str = Field(
        ...,
        min_length=1,
        description="API token from CTFd platform",
    )
    poll_interval: int = Field(
        default=30,
        ge=5,
        le=3600,
        description="Scoreboard polling interval in seconds (5-3600)",
    )
    api_timeout: int = Field(
        default=15,
        ge=1,
        le=120,
        description="API request timeout in seconds (1-120)",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum API retry attempts (0-10)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    ctf_name: str = Field(
        default="",
        description="Human-readable CTF event name",
    )

    @field_validator("ctf_url", mode="before")
    @classmethod
    def validate_ctf_url(cls, v: str) -> str:
        """Normalize CTFd URL to scheme://host — strip any path, query, or fragment.

        CTFd's API is always at <base>/api/v1/..., so passing a URL that
        includes a path like https://demo.ctfd.io/challenges would break
        every API call.  We detect and strip the path automatically.
        """
        if not v:
            raise ValueError("CTF URL must not be empty")

        v = str(v).strip().rstrip("/")

        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError(
                f"CTF URL must start with http:// or https://, got: {v!r}"
            )

        parsed = urlparse(v)

        # Warn and strip if user supplied a path (e.g. /challenges, /login, etc.)
        if parsed.path and parsed.path != "/":
            clean = f"{parsed.scheme}://{parsed.netloc}"
            logger.warning(
                f"CTF URL path stripped: {v!r} → {clean!r}. "
                "The base URL must not include a path; /api/v1/* is appended automatically."
            )
            return clean

        return f"{parsed.scheme}://{parsed.netloc}"

    @field_validator("ctf_token", mode="before")
    @classmethod
    def validate_ctf_token(cls, v: str) -> str:
        """Ensure API token is provided and non-empty."""
        if not v or not str(v).strip():
            raise ValueError("CTF token must not be empty")
        return str(v).strip()

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = str(v).upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}, got {v!r}")
        return upper

    model_config = {"arbitrary_types_allowed": True}


# ─── Config Manager ───────────────────────────────────────────────────────────

class ConfigManager:
    """
    Configuration Manager for CTFd Swiss Army Knife Client.

    Supports two config sources:
      1. .ctf_config.json  — workspace-local JSON config (created by 'ctf init')
      2. .env              — legacy environment file (backward compatible)

    Use resolve_config() to auto-select the appropriate source.
    """

    def __init__(self, config: CTFdConfig):
        """
        Initialize with a pre-validated CTFdConfig instance.

        Args:
            config: Validated CTFdConfig model.
        """
        self.config = config

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def ctf_url(self) -> str:
        """CTFd platform URL."""
        return self.config.ctf_url

    @property
    def api_token(self) -> str:
        """CTFd API token."""
        return self.config.ctf_token

    @property
    def ctf_name(self) -> str:
        """CTF event name."""
        return self.config.ctf_name

    @property
    def poll_interval(self) -> int:
        """Scoreboard polling interval (seconds)."""
        return self.config.poll_interval

    @property
    def api_timeout(self) -> int:
        """API request timeout (seconds)."""
        return self.config.api_timeout

    @property
    def max_retries(self) -> int:
        """Maximum retry attempts for failed requests."""
        return self.config.max_retries

    @property
    def log_level(self) -> str:
        """Logging level string."""
        return self.config.log_level

    @property
    def authorization_header(self) -> dict:
        """Authorization header dict for API requests."""
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type":  "application/json",
        }

    # ── Display ───────────────────────────────────────────────────────────────

    def display_config(self) -> None:
        """
        Display current configuration (token masked for security).
        Calls into ui_renderer to keep concerns separate.
        """
        from src.ui_renderer import render_config_panel
        render_config_panel(self)


# ─── Loaders ─────────────────────────────────────────────────────────────────

def load_from_env(env_path: Optional[Path] = None) -> ConfigManager:
    """
    Load configuration from a .env file.

    Args:
        env_path: Path to .env file. Defaults to .env in current directory.

    Returns:
        Initialized ConfigManager instance.

    Raises:
        FileNotFoundError: If .env file not found.
        ValueError:        If configuration validation fails.
    """
    env_path = Path(env_path or ".env")

    if not env_path.exists():
        raise FileNotFoundError(
            f".env file not found at {env_path.resolve()}.\n"
            "Copy .env.example to .env and fill in your CTFd credentials."
        )

    load_dotenv(env_path, override=True)

    try:
        config = CTFdConfig(
            ctf_url=os.getenv("CTF_URL", ""),
            ctf_token=os.getenv("CTF_TOKEN", ""),
            poll_interval=int(os.getenv("POLL_INTERVAL", 30)),
            api_timeout=int(os.getenv("API_TIMEOUT", 15)),
            max_retries=int(os.getenv("MAX_RETRIES", 3)),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Configuration validation failed: {e}\n"
            "Please check your .env file."
        ) from e

    logger.debug(f"Loaded config from .env: {env_path}")
    return ConfigManager(config)


def load_from_workspace(config_path: Path) -> ConfigManager:
    """
    Load configuration from a .ctf_config.json workspace file.

    Args:
        config_path: Path to .ctf_config.json.

    Returns:
        Initialized ConfigManager instance.

    Raises:
        FileNotFoundError: If config file not found.
        ValueError:        If JSON is malformed or validation fails.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Workspace config not found: {config_path}"
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed .ctf_config.json: {e}") from e

    try:
        config = CTFdConfig(
            ctf_url=raw.get("ctf_url", ""),
            ctf_token=raw.get("ctf_token", ""),
            ctf_name=raw.get("ctf_name", ""),
            poll_interval=int(raw.get("poll_interval", 30)),
            api_timeout=int(raw.get("api_timeout", 15)),
            max_retries=int(raw.get("max_retries", 3)),
            log_level=raw.get("log_level", "INFO"),
        )
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Workspace config validation failed: {e}\n"
            f"Check {config_path}"
        ) from e

    logger.debug(f"Loaded config from workspace: {config_path}")
    return ConfigManager(config)


def resolve_config(env_path: Optional[Path] = None) -> ConfigManager:
    """
    Resolve configuration using the priority cascade:
      1. .ctf_config.json  — auto-detected by walking up the directory tree
      2. .env              — explicit path or default .env in cwd

    Args:
        env_path: Explicit path to .env file (optional, used as fallback).

    Returns:
        Initialized ConfigManager instance.

    Raises:
        FileNotFoundError: If neither config source is found.
        ValueError:        If configuration validation fails.
    """
    from src.workspace_manager import find_workspace_root, WORKSPACE_CONFIG_FILENAME

    # Try workspace config first
    workspace_root = find_workspace_root()
    if workspace_root is not None:
        workspace_config = workspace_root / WORKSPACE_CONFIG_FILENAME
        try:
            mgr = load_from_workspace(workspace_config)
            logger.info(f"Using workspace config: {workspace_config}")
            return mgr
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Workspace config invalid, falling back to .env: {e}")

    # Fall back to .env
    return load_from_env(env_path)


# ── Backward-compat alias ─────────────────────────────────────────────────────

def load_config(env_path: Optional[Path] = None) -> ConfigManager:
    """
    Legacy convenience function — loads from .env.
    New code should prefer resolve_config().
    """
    return load_from_env(env_path)

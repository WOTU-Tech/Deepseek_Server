"""
Application configuration with environment variable overrides and validation.

Supported environment variables:
    OLLAMA_BASE_URL     Ollama API base URL (default: http://localhost:8080/v1)
    DEEPSEEK_MODEL      Model name (default: from utils/parameter.yml, falls back to deepseek-r1:32b)
    FLASK_PORT          Listening port (default: 5000)
    FLASK_HOST          Listening host (default: 127.0.0.1)
    UPLOAD_FOLDER       Upload directory (default: uploads)
    MAX_CONTENT_LENGTH  Max upload size in bytes, e.g. 10485760 (default: 10MB)
    OLLAMA_TIMEOUT      HTTP timeout in seconds (default: 120)
    LOG_LEVEL           Logging level: DEBUG/INFO/WARNING/ERROR (default: INFO)
"""

import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Validated application configuration."""

    ollama_base_url: str = Field(
        default="http://192.168.68.53:8080/v1",
        description="Ollama API base URL",
    )
    model: str = Field(
        default="qwen3.6:35b",
        description="Ollama model name",
    )
    flask_port: int = Field(default=5000, ge=1, le=65535)
    flask_host: str = Field(default="127.0.0.1")
    upload_folder: str = Field(default="uploads")
    max_content_length: int = Field(default=10 * 1024 * 1024, ge=1024)
    ollama_timeout: int = Field(default=120, ge=1)
    log_level: str = Field(default="INFO")

    @field_validator("ollama_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("ollama_base_url must be a valid HTTP(S) URL")
        return v.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ValueError(f"Invalid log level: {v}")
        return v_upper

    @classmethod
    def _env(cls, key: str, default: str) -> str:
        return os.environ.get(key, default)

    @classmethod
    def _env_int(cls, key: str, default: int) -> int:
        raw = os.environ.get(key)
        if raw is not None:
            return int(raw)
        return default

    @classmethod
    def from_env_and_file(cls) -> "AppConfig":
        """Load config from environment variables, falling back to parameter.yml."""
        # Read parameter.yml for model name
        model_from_file: str = "deepseek-r1:32b"
        try:
            config_path = Path(__file__).parent / "parameter.yml"
            if config_path.exists():
                with open(config_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                    model_from_file = str(data.get("model", model_from_file))
        except Exception:
            pass

        # Inspect Field defaults so _env fallbacks stay in sync
        sentinel = ...  # Pydantic's required-field sentinel
        field_defaults = {
            name: info.default
            for name, info in cls.model_fields.items()
            if info.default is not sentinel
        }

        return cls(
            ollama_base_url=cls._env("OLLAMA_BASE_URL", field_defaults["ollama_base_url"]),
            model=cls._env("DEEPSEEK_MODEL", model_from_file),
            flask_port=cls._env_int("FLASK_PORT", field_defaults["flask_port"]),
            flask_host=cls._env("FLASK_HOST", field_defaults["flask_host"]),
            upload_folder=cls._env("UPLOAD_FOLDER", field_defaults["upload_folder"]),
            max_content_length=cls._env_int("MAX_CONTENT_LENGTH", field_defaults["max_content_length"]),
            ollama_timeout=cls._env_int("OLLAMA_TIMEOUT", field_defaults["ollama_timeout"]),
            log_level=cls._env("LOG_LEVEL", field_defaults["log_level"]),
        )

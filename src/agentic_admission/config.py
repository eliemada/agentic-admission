"""Application configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / ``.env`` file.

    Attributes
    ----------
    log_level : str
        Logging verbosity (DEBUG, INFO, WARNING, ERROR).
    model_name : str
        Name of the LLM to use for inference on SCITAS.
    model_base_url : str
        Base URL of the local model serving endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"
    model_name: str = "meta-llama/Llama-3.1-8B-Instruct"
    model_base_url: str = "http://localhost:8000/v1"


settings = Settings()

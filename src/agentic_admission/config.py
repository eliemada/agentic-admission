"""Application configuration via environment variables."""

from __future__ import annotations

from pydantic import field_validator
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
    vlm_model_name : str
        Name of the vision-language model for scanned PDF extraction.
    vlm_base_url : str
        Base URL of the VLM serving endpoint (separate from text LLM).
    presidio_score_threshold : float
        Minimum confidence for PII detection (0.0-1.0).
    gliner_model : str
        GLiNER model ID for zero-shot NER in Presidio.
    anonymizer_excluded_entities_raw : str
        Entity types to preserve (not anonymize), comma-separated.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    log_level: str = "INFO"
    model_name: str = "meta-llama/Llama-3.1-8B-Instruct"
    model_base_url: str = "http://localhost:8000/v1"
    vlm_model_name: str = "Qwen/Qwen3-VL-8B-Instruct"
    vlm_base_url: str = "http://localhost:8001/v1"
    presidio_score_threshold: float = 0.5
    gliner_model: str = "knowledgator/gliner-multitask-large-v0.5"
    anonymizer_excluded_entities_raw: str = "LOCATION,address,NRP,organization,ORGANIZATION"

    # Zero Entropy API for letter retrieval
    zeroentropy_api_key: str = ""
    zeroentropy_collection: str = "mte-reference-letters"

    # OpenRouter for calibration profile generation
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Calibration profiles output directory
    calibration_profiles_dir: str = "data/processed/calibration_profiles"

    # Evaluation output directory
    evaluation_output_dir: str = "data/processed/evaluations"

    @property
    def anonymizer_excluded_entities(self) -> frozenset[str]:
        """Parse comma-separated entity types into a frozenset."""
        return frozenset(
            e.strip()
            for e in self.anonymizer_excluded_entities_raw.split(",")
            if e.strip()
        )


settings = Settings()

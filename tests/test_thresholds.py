"""Tests for the per-entity threshold configuration module."""

from __future__ import annotations

from agentic_admission.anonymizer.thresholds import ThresholdConfig, build_threshold_config


class TestThresholdConfig:
    """Tests for the frozen ThresholdConfig dataclass."""

    def test_frozen(self) -> None:
        config = build_threshold_config()
        try:
            config.fallback = 0.99  # type: ignore[misc]
            msg = "ThresholdConfig should be frozen"
            raise AssertionError(msg)
        except AttributeError:
            pass  # Expected — frozen dataclass

    def test_known_entity_threshold(self) -> None:
        config = build_threshold_config()
        assert config.get_threshold("PERSON") == 0.6

    def test_email_low_threshold(self) -> None:
        config = build_threshold_config()
        assert config.get_threshold("EMAIL_ADDRESS") == 0.4

    def test_nrp_very_high_threshold(self) -> None:
        config = build_threshold_config()
        assert config.get_threshold("NRP") == 0.65

    def test_unknown_entity_uses_fallback(self) -> None:
        config = build_threshold_config()
        assert config.get_threshold("UNKNOWN_ENTITY_XYZ") == config.fallback

    def test_default_fallback_value(self) -> None:
        config = build_threshold_config()
        assert config.fallback == 0.5


class TestBuildThresholdConfig:
    """Tests for the factory function."""

    def test_override_existing_entity(self) -> None:
        config = build_threshold_config(overrides={"PERSON": 0.9})
        assert config.get_threshold("PERSON") == 0.9

    def test_override_adds_new_entity(self) -> None:
        config = build_threshold_config(overrides={"CUSTOM_ENTITY": 0.42})
        assert config.get_threshold("CUSTOM_ENTITY") == 0.42

    def test_custom_fallback(self) -> None:
        config = build_threshold_config(fallback=0.7)
        assert config.fallback == 0.7
        assert config.get_threshold("UNKNOWN") == 0.7

    def test_returns_threshold_config_type(self) -> None:
        config = build_threshold_config()
        assert isinstance(config, ThresholdConfig)

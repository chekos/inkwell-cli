"""Tests for TranscriptionManager dependency injection and configuration.

This test suite validates the parameter precedence logic for backward-compatible
dependency injection, ensuring config objects take precedence over individual params.
"""

import warnings

import pytest

from inkwell.config.schema import TranscriptionConfig
from inkwell.transcription.gemini import GeminiTranscriber
from inkwell.transcription.manager import TranscriptionManager
from inkwell.utils.costs import CostTracker


class TestTranscriptionManagerConfigInjection:
    """Test configuration dependency injection patterns."""

    def test_config_object_only(self) -> None:
        """Using only config object works correctly."""
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",
            api_key="test-key-from-config-1234567890",
            cost_threshold_usd=2.0,
        )

        manager = TranscriptionManager(config=config)

        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"
        assert manager.gemini_transcriber.cost_threshold_usd == 2.0

    def test_individual_params_only(self) -> None:
        """Using only individual params works (backward compatibility)."""
        manager = TranscriptionManager(
            gemini_api_key="test-key-individual-1234567890", model_name="gemini-1.5-flash"
        )

        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-1.5-flash"

    def test_config_overrides_individual_params(self) -> None:
        """Config object takes precedence over individual params.

        This is the critical test that catches bug #046 - when both config
        and individual params are provided, config should win.
        """
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash", api_key="config-key-1234567890123456"
        )

        manager = TranscriptionManager(
            config=config,
            gemini_api_key="deprecated-key-1234567890",
            model_name="gemini-1.5-flash",  # Should be ignored
        )

        # Config values should win
        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"
        # NOT "gemini-1.5-flash"

    def test_config_none_values_fall_back_to_params(self) -> None:
        """When config has None values, falls back to individual params."""
        config = TranscriptionConfig(
            api_key=None,  # Explicit None
            model_name="gemini-2.5-flash",
        )

        manager = TranscriptionManager(
            config=config, gemini_api_key="fallback-key-123456789012345678901234567890"
        )

        # Should use config model_name but fallback api_key
        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"

    def test_empty_config_uses_defaults(self) -> None:
        """Empty config object uses default values."""
        config = TranscriptionConfig(
            api_key="test-api-key-1234567890123456789012345678901234567890"
        )  # All defaults except API key

        manager = TranscriptionManager(config=config)

        # Should use defaults from TranscriptionConfig
        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"
        assert manager.gemini_transcriber.cost_threshold_usd == 1.0

    def test_no_config_no_params_tries_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no config and no params, tries environment variables."""
        # Clear environment variable to ensure predictable behavior
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        manager = TranscriptionManager()

        # Should create transcriber as None since no API key available
        assert manager.gemini_transcriber is None

    def test_no_config_no_params_uses_environment_if_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With environment variable set, creates transcriber from env."""
        monkeypatch.setenv("GOOGLE_API_KEY", "env-api-key-1234567890123456789012345678901234567890")

        manager = TranscriptionManager()

        # Should create transcriber from environment
        assert manager.gemini_transcriber is not None
        assert isinstance(manager.gemini_transcriber, GeminiTranscriber)

    def test_injected_transcriber_takes_precedence(self) -> None:
        """Injected transcriber instance overrides config."""
        custom_transcriber = GeminiTranscriber(
            api_key="injected-key-12345678901234567890123456789012345678901234567890",
            model_name="gemini-1.5-flash",
        )

        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",
            api_key="config-key-123456789012345678901234567890123456789012345678901234567890",
        )

        manager = TranscriptionManager(config=config, gemini_transcriber=custom_transcriber)

        # Injected instance should be used directly
        assert manager.gemini_transcriber is custom_transcriber
        assert manager.gemini_transcriber.model_name == "gemini-1.5-flash"

    def test_config_with_all_values_set(self) -> None:
        """Config with all values explicitly set works correctly."""
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",
            api_key="full-config-key-123456789012345678901234567890123456789012345678901234567890",
            cost_threshold_usd=5.0,
            youtube_check=False,
        )

        manager = TranscriptionManager(config=config)

        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"
        assert manager.gemini_transcriber.cost_threshold_usd == 5.0


class TestTranscriptionManagerCostTracker:
    """Test cost tracker dependency injection."""

    def test_cost_tracker_injection(self) -> None:
        """Cost tracker can be injected for tracking."""
        tracker = CostTracker()
        config = TranscriptionConfig(
            api_key="test-key-123456789012345678901234567890123456789012345678901234567890"
        )

        manager = TranscriptionManager(config=config, cost_tracker=tracker)

        assert manager.cost_tracker is tracker

    def test_no_cost_tracker_works(self) -> None:
        """Manager works without cost tracker (optional)."""
        config = TranscriptionConfig(
            api_key="test-key-123456789012345678901234567890123456789012345678901234567890"
        )

        manager = TranscriptionManager(config=config)

        assert manager.cost_tracker is None

    def test_cost_tracker_without_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cost tracker works with individual params (backward compat)."""
        tracker = CostTracker()

        manager = TranscriptionManager(
            gemini_api_key="test-key-123456789012345678901234567890123456789012345678901234567890",
            cost_tracker=tracker,
        )

        assert manager.cost_tracker is tracker
        assert manager.gemini_transcriber is not None


class TestTranscriptionManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_config_overrides_only_model_name(self) -> None:
        """Config overrides only model_name, uses param for api_key."""
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",
            api_key=None,  # Explicitly None
        )

        manager = TranscriptionManager(
            config=config,
            gemini_api_key="param-key-1234567890123456789012345678901234567890123456789012345678901234567890",
        )

        assert manager.gemini_transcriber is not None
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"

    def test_config_overrides_only_api_key(self) -> None:
        """Config overrides only api_key, uses param for model_name."""
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",  # Default, but explicit
            api_key="config-key-12345678901234567890123456789012345678901234567890123456789012345678901234567890",
        )

        manager = TranscriptionManager(
            config=config,
            model_name="gemini-1.5-flash",  # Should be overridden
        )

        assert manager.gemini_transcriber is not None
        # Config model_name should win (even if it's the default)
        assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"

    def test_multiple_initialization_paths(self) -> None:
        """Verify multiple initialization paths don't interfere."""
        # Path 1: Config only
        config1 = TranscriptionConfig(
            api_key="config1-key-1234567890123456789012345678901234567890123456789012345678901234567890",
            model_name="gemini-2.5-flash",
        )
        manager1 = TranscriptionManager(config=config1)
        assert manager1.gemini_transcriber is not None
        assert manager1.gemini_transcriber.model_name == "gemini-2.5-flash"

        # Path 2: Params only
        manager2 = TranscriptionManager(
            gemini_api_key="params-key-123456789012345678901234567890123456789012345678901234567890",
            model_name="gemini-1.5-flash",
        )
        assert manager2.gemini_transcriber is not None
        assert manager2.gemini_transcriber.model_name == "gemini-1.5-flash"

        # Path 3: Both (config wins)
        config3 = TranscriptionConfig(
            api_key="config3-key-1234567890123456789012345678901234567890123456789012345678901234567890",
            model_name="gemini-2.5-flash",
        )
        manager3 = TranscriptionManager(
            config=config3,
            gemini_api_key="params-key-123456789012345678901234567890123456789012345678901234567890",
            model_name="gemini-1.5-flash",
        )
        assert manager3.gemini_transcriber is not None
        assert manager3.gemini_transcriber.model_name == "gemini-2.5-flash"

        # Verify managers are independent
        assert manager1.gemini_transcriber is not manager2.gemini_transcriber
        assert manager2.gemini_transcriber is not manager3.gemini_transcriber


class TestTranscriptionManagerDeprecationWarnings:
    """Test deprecation warnings for individual parameters."""

    def test_deprecated_params_trigger_warning(self) -> None:
        """Using deprecated individual params should trigger DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            manager = TranscriptionManager(
                gemini_api_key="test-key-1234567890123456789012345678901234567890",
                model_name="gemini-1.5-flash",
            )

            # Should have triggered exactly one warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "TranscriptionConfig" in str(w[0].message)
            assert "v2.0" in str(w[0].message)

    def test_config_object_no_warning(self) -> None:
        """Using config object should NOT trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            config = TranscriptionConfig(
                api_key="test-key-1234567890123456789012345678901234567890"
            )
            manager = TranscriptionManager(config=config)

            # Should have no warnings
            assert len(w) == 0

    def test_only_gemini_api_key_warns(self) -> None:
        """Using only gemini_api_key should trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            manager = TranscriptionManager(
                gemini_api_key="test-key-1234567890123456789012345678901234567890"
            )

            # Should have triggered warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "gemini_api_key" in str(w[0].message)

    def test_only_model_name_warns(self) -> None:
        """Using only model_name should trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            manager = TranscriptionManager(model_name="gemini-1.5-flash")

            # Should have triggered warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "model_name" in str(w[0].message)

    def test_config_with_individual_params_no_warning(self) -> None:
        """When config is provided, no warning even if deprecated params present.

        This is by design - if user provides config, they're using the new pattern.
        Individual params might be there for legacy reasons but config takes precedence.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            config = TranscriptionConfig(
                api_key="config-key-1234567890123456789012345678901234567890"
            )
            manager = TranscriptionManager(
                config=config, gemini_api_key="param-key-1234567890123456789012345678901234567890"
            )

            # Should have no warnings (config is provided)
            assert len(w) == 0

    def test_no_params_no_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Using no params should not trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Clear environment to avoid creating transcriber
            monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

            manager = TranscriptionManager()

            # Should have no warnings
            assert len(w) == 0

    def test_warning_message_includes_migration_info(self) -> None:
        """Warning message should include what to use instead."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            manager = TranscriptionManager(
                gemini_api_key="test-key-1234567890123456789012345678901234567890"
            )

            # Verify warning message is helpful
            warning_msg = str(w[0].message)
            assert "TranscriptionConfig" in warning_msg
            assert "v2.0" in warning_msg
            assert "deprecated" in warning_msg.lower()

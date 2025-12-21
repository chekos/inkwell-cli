"""Tests for configuration precedence resolution.

Tests the standardized parameter precedence logic used across all services
to ensure config > param > default resolution is consistent and correct.
"""

from inkwell.config.precedence import resolve_config_value


class TestConfigPrecedence:
    """Test configuration value precedence resolution."""

    def test_config_value_takes_precedence(self):
        """Config value should win over param and default."""
        result = resolve_config_value(
            config_value="config", param_value="param", default_value="default"
        )
        assert result == "config"

    def test_param_value_when_config_none(self):
        """Param value should win when config is None."""
        result = resolve_config_value(
            config_value=None, param_value="param", default_value="default"
        )
        assert result == "param"

    def test_default_when_both_none(self):
        """Default should be used when both config and param are None."""
        result = resolve_config_value(config_value=None, param_value=None, default_value="default")
        assert result == "default"

    def test_zero_is_valid_value(self):
        """Zero should not be treated as None."""
        result = resolve_config_value(config_value=0, param_value=5, default_value=10)
        assert result == 0  # Not 5 or 10

    def test_empty_string_is_valid(self):
        """Empty string should not be treated as None."""
        result = resolve_config_value(config_value="", param_value="param", default_value="default")
        assert result == ""  # Not "param" or "default"

    def test_false_is_valid_value(self):
        """False should not be treated as None."""
        result = resolve_config_value(config_value=False, param_value=True, default_value=True)
        assert result is False  # Not True

    def test_none_explicitly_as_default(self):
        """None can be used as a default value."""
        result = resolve_config_value(config_value=None, param_value=None, default_value=None)
        assert result is None

    def test_config_zero_overrides_param_nonzero(self):
        """Config value of 0 should override non-zero param."""
        result = resolve_config_value(config_value=0, param_value=100, default_value=50)
        assert result == 0

    def test_param_zero_overrides_default_nonzero(self):
        """Param value of 0 should override non-zero default."""
        result = resolve_config_value(config_value=None, param_value=0, default_value=100)
        assert result == 0

    def test_config_empty_string_overrides_param(self):
        """Config empty string should override non-empty param."""
        result = resolve_config_value(
            config_value="", param_value="non-empty", default_value="default"
        )
        assert result == ""

    def test_param_empty_string_overrides_default(self):
        """Param empty string should override non-empty default."""
        result = resolve_config_value(config_value=None, param_value="", default_value="default")
        assert result == ""

    def test_config_false_overrides_param_true(self):
        """Config False should override param True."""
        result = resolve_config_value(config_value=False, param_value=True, default_value=True)
        assert result is False

    def test_param_false_overrides_default_true(self):
        """Param False should override default True."""
        result = resolve_config_value(config_value=None, param_value=False, default_value=True)
        assert result is False

    def test_float_values(self):
        """Test with float values including 0.0."""
        # Config wins
        assert resolve_config_value(1.5, 2.5, 3.5) == 1.5

        # Param wins when config None
        assert resolve_config_value(None, 2.5, 3.5) == 2.5

        # 0.0 is valid
        assert resolve_config_value(0.0, 2.5, 3.5) == 0.0
        assert resolve_config_value(None, 0.0, 3.5) == 0.0

    def test_list_values(self):
        """Test with list values including empty lists."""
        # Config wins
        assert resolve_config_value([1, 2], [3, 4], [5, 6]) == [1, 2]

        # Param wins when config None
        assert resolve_config_value(None, [3, 4], [5, 6]) == [3, 4]

        # Empty list is valid
        assert resolve_config_value([], [3, 4], [5, 6]) == []
        assert resolve_config_value(None, [], [5, 6]) == []

    def test_dict_values(self):
        """Test with dict values including empty dicts."""
        # Config wins
        assert resolve_config_value({"a": 1}, {"b": 2}, {"c": 3}) == {"a": 1}

        # Param wins when config None
        assert resolve_config_value(None, {"b": 2}, {"c": 3}) == {"b": 2}

        # Empty dict is valid
        assert resolve_config_value({}, {"b": 2}, {"c": 3}) == {}
        assert resolve_config_value(None, {}, {"c": 3}) == {}

    def test_complex_types(self):
        """Test with complex object types."""

        class CustomObj:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return isinstance(other, CustomObj) and self.value == other.value

        obj1 = CustomObj(1)
        obj2 = CustomObj(2)
        obj3 = CustomObj(3)

        # Config wins
        assert resolve_config_value(obj1, obj2, obj3) == obj1

        # Param wins when config None
        assert resolve_config_value(None, obj2, obj3) == obj2

    def test_type_consistency(self):
        """Verify types are preserved through resolution."""
        # String
        result = resolve_config_value("config", "param", "default")
        assert isinstance(result, str)

        # Int
        result = resolve_config_value(1, 2, 3)
        assert isinstance(result, int)

        # Float
        result = resolve_config_value(1.0, 2.0, 3.0)
        assert isinstance(result, float)

        # Bool
        result = resolve_config_value(True, False, False)
        assert isinstance(result, bool)

        # List
        result = resolve_config_value([1], [2], [3])
        assert isinstance(result, list)

        # Dict
        result = resolve_config_value({}, {}, {})
        assert isinstance(result, dict)

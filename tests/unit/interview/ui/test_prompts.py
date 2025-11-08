"""Tests for interview UI prompts and input handlers."""

from unittest.mock import patch

import pytest

from inkwell.interview.ui.prompts import (
    UserCommand,
    confirm_action,
    display_help,
    get_choice,
    get_multiline_input,
    get_single_line_input,
)


@pytest.fixture
def mock_console():
    """Mock Rich console for testing."""
    with patch("inkwell.interview.ui.prompts.console") as mock:
        yield mock


# UserCommand Tests


def test_user_command_constants():
    """Test UserCommand has expected constants."""
    assert UserCommand.SKIP == "skip"
    assert UserCommand.DONE == "done"
    assert UserCommand.QUIT == "quit"
    assert UserCommand.HELP == "help"

    assert UserCommand.SKIP in UserCommand.ALL_COMMANDS
    assert UserCommand.DONE in UserCommand.ALL_COMMANDS
    assert UserCommand.QUIT in UserCommand.ALL_COMMANDS
    assert UserCommand.HELP in UserCommand.ALL_COMMANDS


# Multiline Input Tests


def test_get_multiline_input_with_text(mock_console):
    """Test getting multiline input with actual text."""
    # Simulate user typing two lines then Ctrl-D
    with patch("builtins.input", side_effect=["Line 1", "Line 2", EOFError]):
        result = get_multiline_input()

    assert result == "Line 1\nLine 2"


def test_get_multiline_input_skip_command(mock_console):
    """Test skip command on first line."""
    with patch("builtins.input", return_value="skip"):
        result = get_multiline_input()

    assert result == "skip"


def test_get_multiline_input_done_command(mock_console):
    """Test done command."""
    with patch("builtins.input", return_value="done"):
        result = get_multiline_input()

    assert result == "done"


def test_get_multiline_input_quit_command(mock_console):
    """Test quit command."""
    with patch("builtins.input", return_value="quit"):
        result = get_multiline_input()

    assert result == "quit"


def test_get_multiline_input_help_command(mock_console):
    """Test help command."""
    with patch("builtins.input", return_value="help"):
        result = get_multiline_input()

    assert result == "help"


def test_get_multiline_input_case_insensitive(mock_console):
    """Test commands are case-insensitive."""
    with patch("builtins.input", return_value="SKIP"):
        result = get_multiline_input()

    assert result == "skip"


def test_get_multiline_input_double_enter(mock_console):
    """Test double enter to submit."""
    # User types text, empty line, empty line
    with patch("builtins.input", side_effect=["Some text", "", ""]):
        result = get_multiline_input()

    assert result == "Some text"


def test_get_multiline_input_ctrl_d_submit(mock_console):
    """Test Ctrl-D (EOF) submits input."""
    with patch("builtins.input", side_effect=["First line", "Second line", EOFError]):
        result = get_multiline_input()

    assert result == "First line\nSecond line"


def test_get_multiline_input_empty_returns_skip(mock_console):
    """Test empty input returns 'skip' when not allowed."""
    with patch("builtins.input", side_effect=[EOFError]):
        result = get_multiline_input(allow_empty=False)

    assert result == "skip"


def test_get_multiline_input_empty_allowed(mock_console):
    """Test empty input allowed when specified."""
    with patch("builtins.input", side_effect=[EOFError]):
        result = get_multiline_input(allow_empty=True)

    assert result == ""


def test_get_multiline_input_ctrl_c_cancel(mock_console):
    """Test Ctrl-C cancels input."""
    # First Ctrl-C, then confirm yes (default False so need to mock Confirm)
    with patch("builtins.input", side_effect=[KeyboardInterrupt]):
        with patch("inkwell.interview.ui.prompts.Confirm.ask", return_value=True):
            result = get_multiline_input()

    assert result is None


def test_get_multiline_input_ctrl_c_resume(mock_console):
    """Test Ctrl-C can be cancelled to resume."""
    # Ctrl-C, decline cancellation, then type text, then EOF
    with patch("builtins.input", side_effect=[KeyboardInterrupt, "Resumed text", EOFError]):
        with patch("inkwell.interview.ui.prompts.Confirm.ask", return_value=False):
            result = get_multiline_input()

    assert result == "Resumed text"


def test_get_multiline_input_strips_trailing_empty_lines(mock_console):
    """Test trailing empty lines are removed."""
    with patch("builtins.input", side_effect=["Text", "", "", "", EOFError]):
        result = get_multiline_input()

    assert result == "Text"


def test_get_multiline_input_command_only_on_first_line(mock_console):
    """Test commands only work on first line."""
    # Type some text first, then "skip" - should not be treated as command
    with patch("builtins.input", side_effect=["Some text", "skip", EOFError]):
        result = get_multiline_input()

    assert "skip" in result
    assert result != "skip"


def test_get_multiline_input_custom_prompt(mock_console):
    """Test custom prompt text."""
    with patch("builtins.input", side_effect=[EOFError]):
        get_multiline_input(prompt="Custom prompt", allow_empty=True)

    # Check that console.print was called with custom prompt
    print_calls = [str(call) for call in mock_console.print.call_args_list]
    assert any("Custom prompt" in call for call in print_calls)


def test_get_multiline_input_no_instructions(mock_console):
    """Test hiding input instructions."""
    with patch("builtins.input", side_effect=[EOFError]):
        get_multiline_input(show_instructions=False, allow_empty=True)

    # Should still work, just different display


# Single Line Input Tests


def test_get_single_line_input_basic(mock_console):
    """Test single line input."""
    with patch("builtins.input", return_value="  test input  "):
        result = get_single_line_input("Enter something")

    assert result == "test input"  # Should be stripped


def test_get_single_line_input_with_default(mock_console):
    """Test single line input with default value."""
    # Empty input should use default
    with patch("builtins.input", return_value=""):
        result = get_single_line_input("Enter name", default="default_value")

    assert result == "default_value"


def test_get_single_line_input_ctrl_c(mock_console):
    """Test Ctrl-C cancels single line input."""
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = get_single_line_input("Enter something")

    assert result is None


def test_get_single_line_input_eof(mock_console):
    """Test EOF returns default."""
    with patch("builtins.input", side_effect=EOFError):
        result = get_single_line_input("Enter something", default="default")

    assert result == "default"


# Choice Input Tests


def test_get_choice_by_number(mock_console):
    """Test selecting choice by number."""
    choices = ["option1", "option2", "option3"]

    with patch("builtins.input", return_value="2"):
        result = get_choice("Select option", choices)

    assert result == "option2"


def test_get_choice_by_text(mock_console):
    """Test selecting choice by text."""
    choices = ["reflective", "analytical", "creative"]

    with patch("builtins.input", return_value="analytical"):
        result = get_choice("Select template", choices)

    assert result == "analytical"


def test_get_choice_with_default(mock_console):
    """Test choice with default value."""
    choices = ["a", "b", "c"]

    # Empty input should use default
    with patch("builtins.input", return_value=""):
        result = get_choice("Choose", choices, default="b")

    assert result == "b"


def test_get_choice_invalid_then_valid(mock_console):
    """Test retrying after invalid choice."""
    choices = ["a", "b", "c"]

    # First invalid, then valid
    with patch("builtins.input", side_effect=["99", "2"]):
        result = get_choice("Choose", choices)

    assert result == "b"


def test_get_choice_ctrl_c(mock_console):
    """Test Ctrl-C cancels choice."""
    choices = ["a", "b", "c"]

    with patch("builtins.input", side_effect=KeyboardInterrupt):
        result = get_choice("Choose", choices)

    assert result is None


def test_get_choice_eof_with_default(mock_console):
    """Test EOF returns default."""
    choices = ["a", "b", "c"]

    with patch("builtins.input", side_effect=EOFError):
        result = get_choice("Choose", choices, default="a")

    assert result == "a"


# Confirm Action Tests


def test_confirm_action_yes(mock_console):
    """Test confirming action with yes."""
    with patch("inkwell.interview.ui.prompts.Confirm.ask", return_value=True):
        result = confirm_action("Are you sure?")

    assert result is True


def test_confirm_action_no(mock_console):
    """Test declining action with no."""
    with patch("inkwell.interview.ui.prompts.Confirm.ask", return_value=False):
        result = confirm_action("Delete everything?")

    assert result is False


def test_confirm_action_with_default(mock_console):
    """Test confirm with default value."""
    with patch("inkwell.interview.ui.prompts.Confirm.ask", return_value=True) as mock_confirm:
        confirm_action("Continue?", default=True)

        # Check that default was passed
        mock_confirm.assert_called_once()
        assert mock_confirm.call_args[1]["default"] is True


# Display Help Tests


def test_display_help(mock_console):
    """Test displaying help message."""
    display_help()

    # Should print help text
    assert mock_console.print.call_count == 2

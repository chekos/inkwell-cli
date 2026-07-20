"""Agent-runtime model tests."""

import pytest
from pydantic import ValidationError

from inkwell.agent_runtime.models import RuntimeBilling, RuntimeRequest, RuntimeUsage


def test_runtime_managed_billing_is_unknown_not_zero() -> None:
    billing = RuntimeBilling(mode="runtime_managed", amount_usd=None)

    assert billing.amount_usd is None
    with pytest.raises(ValidationError):
        RuntimeBilling(mode="runtime_managed", amount_usd=0.0)


def test_known_and_estimated_billing_require_an_amount() -> None:
    with pytest.raises(ValidationError):
        RuntimeBilling(mode="known")
    with pytest.raises(ValidationError):
        RuntimeBilling(mode="estimated")


def test_explicit_model_is_required() -> None:
    with pytest.raises(ValidationError):
        RuntimeRequest(prompt="task", output_schema={"type": "object"}, requested_model=" ")


def test_usage_total_excludes_cached_input_duplication() -> None:
    usage = RuntimeUsage(input_tokens=10, cached_input_tokens=4, output_tokens=3)

    assert usage.total_tokens == 13

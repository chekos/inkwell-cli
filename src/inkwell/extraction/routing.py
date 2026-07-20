"""Token-aware extraction routing policy."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jinja2 import Template

from inkwell.plugins.types import ExtractionCapabilities

from .models import ExtractionTemplate


@dataclass(frozen=True)
class ExtractionRoutingAttempt:
    """One ordered extraction provider/model attempt."""

    provider: str
    model: str
    estimated_prompt_tokens: int
    reason: str


class ExtractionRoutingPolicy:
    """Plan ordered extraction attempts from prompt size and provider capabilities."""

    def estimate_prompt_tokens(
        self,
        *,
        template: ExtractionTemplate,
        transcript: str,
        metadata: Mapping[str, Any],
    ) -> int:
        """Estimate input plus expected output tokens for a template request."""
        rendered_prompt = self._render_user_prompt(template, transcript, metadata)
        prompt_text = "\n\n".join([template.system_prompt, rendered_prompt])
        return max(1, len(prompt_text) // 4) + template.max_tokens

    def plan(
        self,
        *,
        template: ExtractionTemplate,
        transcript: str,
        metadata: Mapping[str, Any],
        available_capabilities: Mapping[str, ExtractionCapabilities],
        default_provider: str,
        override: str | None = None,
    ) -> list[ExtractionRoutingAttempt]:
        """Return ordered provider/model attempts that can fit the prompt."""
        estimated_tokens = self.estimate_prompt_tokens(
            template=template,
            transcript=transcript,
            metadata=metadata,
        )
        candidates = self._candidate_order(template, default_provider, override)
        attempts: list[ExtractionRoutingAttempt] = []

        for provider in candidates:
            capabilities = available_capabilities.get(provider)
            if capabilities is None:
                continue
            if capabilities.max_input_tokens is not None:
                if estimated_tokens > capabilities.max_input_tokens:
                    continue
            attempts.append(
                ExtractionRoutingAttempt(
                    provider=provider,
                    model=capabilities.model_name,
                    estimated_prompt_tokens=estimated_tokens,
                    reason="override" if override else "auto",
                )
            )

        return attempts

    def _candidate_order(
        self,
        template: ExtractionTemplate,
        default_provider: str,
        override: str | None,
    ) -> list[str]:
        """Build a deduplicated candidate order before capability filtering."""
        if override:
            return [override]

        candidates: list[str] = []
        if template.model_preference and template.model_preference != "codex":
            candidates.append(template.model_preference)

        if "quote" in template.name.lower():
            candidates.extend(["claude", default_provider, "gemini"])
        elif template.expected_format == "json" and template.output_schema:
            required_fields = template.output_schema.get("required", [])
            if len(required_fields) > 5:
                candidates.extend(["claude", default_provider, "gemini"])
            else:
                candidates.extend([default_provider, "gemini", "claude"])
        else:
            candidates.extend([default_provider, "gemini", "claude"])

        return self._dedupe(candidates)

    @staticmethod
    def _dedupe(values: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _render_user_prompt(
        template: ExtractionTemplate,
        transcript: str,
        metadata: Mapping[str, Any],
    ) -> str:
        examples_text = ""
        if template.few_shot_examples:
            examples_text = "\n\nExamples:\n"
            for i, example in enumerate(template.few_shot_examples, 1):
                examples_text += f"\nExample {i}:\n"
                if "input" in example:
                    examples_text += f"Input: {example['input']}\n"
                if "output" in example:
                    examples_text += f"Output:\n{json.dumps(example['output'], indent=2)}\n"

        prompt = Template(template.user_prompt_template).render(
            transcript=transcript,
            metadata=dict(metadata),
            examples=examples_text,
        )
        if examples_text:
            return examples_text + "\n\n" + prompt
        return prompt

"""Tests for interview templates."""

import pytest

from inkwell.interview.models import InterviewTemplate
from inkwell.interview.templates import (
    ANALYTICAL_TEMPLATE,
    CREATIVE_TEMPLATE,
    REFLECTIVE_TEMPLATE,
    TEMPLATES,
    get_template,
    get_template_description,
    list_templates,
)

# Template Content Tests


def test_reflective_template_exists():
    """Test that reflective template is defined."""
    assert REFLECTIVE_TEMPLATE is not None
    assert isinstance(REFLECTIVE_TEMPLATE, InterviewTemplate)
    assert REFLECTIVE_TEMPLATE.name == "reflective"


def test_analytical_template_exists():
    """Test that analytical template is defined."""
    assert ANALYTICAL_TEMPLATE is not None
    assert isinstance(ANALYTICAL_TEMPLATE, InterviewTemplate)
    assert ANALYTICAL_TEMPLATE.name == "analytical"


def test_creative_template_exists():
    """Test that creative template is defined."""
    assert CREATIVE_TEMPLATE is not None
    assert isinstance(CREATIVE_TEMPLATE, InterviewTemplate)
    assert CREATIVE_TEMPLATE.name == "creative"


def test_reflective_template_structure():
    """Test reflective template has all required fields."""
    assert REFLECTIVE_TEMPLATE.name == "reflective"
    assert REFLECTIVE_TEMPLATE.description
    assert REFLECTIVE_TEMPLATE.system_prompt
    assert REFLECTIVE_TEMPLATE.initial_question_prompt
    assert REFLECTIVE_TEMPLATE.follow_up_prompt
    assert REFLECTIVE_TEMPLATE.conclusion_prompt
    assert REFLECTIVE_TEMPLATE.target_questions == 5
    assert REFLECTIVE_TEMPLATE.max_depth == 3
    assert REFLECTIVE_TEMPLATE.temperature == 0.7


def test_analytical_template_structure():
    """Test analytical template has all required fields."""
    assert ANALYTICAL_TEMPLATE.name == "analytical"
    assert ANALYTICAL_TEMPLATE.description
    assert ANALYTICAL_TEMPLATE.system_prompt
    assert ANALYTICAL_TEMPLATE.initial_question_prompt
    assert ANALYTICAL_TEMPLATE.follow_up_prompt
    assert ANALYTICAL_TEMPLATE.conclusion_prompt
    assert ANALYTICAL_TEMPLATE.target_questions == 5
    assert ANALYTICAL_TEMPLATE.max_depth == 3
    assert ANALYTICAL_TEMPLATE.temperature == 0.7


def test_creative_template_structure():
    """Test creative template has all required fields."""
    assert CREATIVE_TEMPLATE.name == "creative"
    assert CREATIVE_TEMPLATE.description
    assert CREATIVE_TEMPLATE.system_prompt
    assert CREATIVE_TEMPLATE.initial_question_prompt
    assert CREATIVE_TEMPLATE.follow_up_prompt
    assert CREATIVE_TEMPLATE.conclusion_prompt
    assert CREATIVE_TEMPLATE.target_questions == 5
    assert CREATIVE_TEMPLATE.max_depth == 3
    assert CREATIVE_TEMPLATE.temperature == 0.8  # Higher for creativity


def test_reflective_template_prompts():
    """Test reflective template has appropriate guidance."""
    # System prompt should mention reflection
    assert "reflect" in REFLECTIVE_TEMPLATE.system_prompt.lower()
    assert "personal" in REFLECTIVE_TEMPLATE.system_prompt.lower()

    # Should have clear guidelines
    assert "Guidelines:" in REFLECTIVE_TEMPLATE.system_prompt
    assert "open-ended" in REFLECTIVE_TEMPLATE.system_prompt.lower()


def test_analytical_template_prompts():
    """Test analytical template has appropriate guidance."""
    # System prompt should mention analysis
    assert "analytical" in ANALYTICAL_TEMPLATE.system_prompt.lower()
    assert "critical" in ANALYTICAL_TEMPLATE.system_prompt.lower()

    # Should encourage critical thinking
    assert "evaluate" in ANALYTICAL_TEMPLATE.initial_question_prompt.lower()


def test_creative_template_prompts():
    """Test creative template has appropriate guidance."""
    # System prompt should mention creativity
    assert "creative" in CREATIVE_TEMPLATE.system_prompt.lower()
    assert "imagination" in CREATIVE_TEMPLATE.system_prompt.lower()

    # Should encourage connections
    assert "connection" in CREATIVE_TEMPLATE.initial_question_prompt.lower()


# Template Registry Tests


def test_templates_registry():
    """Test that TEMPLATES registry contains all templates."""
    assert len(TEMPLATES) == 3
    assert "reflective" in TEMPLATES
    assert "analytical" in TEMPLATES
    assert "creative" in TEMPLATES


def test_templates_registry_values():
    """Test that registry values are correct templates."""
    assert TEMPLATES["reflective"] == REFLECTIVE_TEMPLATE
    assert TEMPLATES["analytical"] == ANALYTICAL_TEMPLATE
    assert TEMPLATES["creative"] == CREATIVE_TEMPLATE


# get_template Tests


def test_get_template_reflective():
    """Test getting reflective template by name."""
    template = get_template("reflective")
    assert template == REFLECTIVE_TEMPLATE


def test_get_template_analytical():
    """Test getting analytical template by name."""
    template = get_template("analytical")
    assert template == ANALYTICAL_TEMPLATE


def test_get_template_creative():
    """Test getting creative template by name."""
    template = get_template("creative")
    assert template == CREATIVE_TEMPLATE


def test_get_template_invalid_name():
    """Test that getting invalid template raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        get_template("nonexistent")

    assert "Unknown template: nonexistent" in str(exc_info.value)
    assert "Available: " in str(exc_info.value)


def test_get_template_error_message_shows_available():
    """Test that error message lists available templates."""
    with pytest.raises(ValueError) as exc_info:
        get_template("invalid")

    error_msg = str(exc_info.value)
    assert "reflective" in error_msg
    assert "analytical" in error_msg
    assert "creative" in error_msg


# list_templates Tests


def test_list_templates():
    """Test listing all template names."""
    templates = list_templates()

    assert isinstance(templates, list)
    assert len(templates) == 3
    assert "reflective" in templates
    assert "analytical" in templates
    assert "creative" in templates


def test_list_templates_returns_copy():
    """Test that list_templates returns a new list each time."""
    list1 = list_templates()
    list2 = list_templates()

    # Should be equal but not the same object
    assert list1 == list2
    assert list1 is not list2


# get_template_description Tests


def test_get_template_description_reflective():
    """Test getting reflective template description."""
    desc = get_template_description("reflective")

    assert desc == REFLECTIVE_TEMPLATE.description
    assert "reflection" in desc.lower()


def test_get_template_description_analytical():
    """Test getting analytical template description."""
    desc = get_template_description("analytical")

    assert desc == ANALYTICAL_TEMPLATE.description
    assert "analysis" in desc.lower() or "analytical" in desc.lower()


def test_get_template_description_creative():
    """Test getting creative template description."""
    desc = get_template_description("creative")

    assert desc == CREATIVE_TEMPLATE.description
    assert "creative" in desc.lower()


def test_get_template_description_invalid():
    """Test that getting description for invalid template raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        get_template_description("invalid")

    assert "Unknown template" in str(exc_info.value)


# Template Characteristics Tests


def test_templates_have_unique_names():
    """Test that all templates have unique names."""
    names = [t.name for t in TEMPLATES.values()]
    assert len(names) == len(set(names))


def test_templates_have_unique_descriptions():
    """Test that all templates have unique descriptions."""
    descriptions = [t.description for t in TEMPLATES.values()]
    assert len(descriptions) == len(set(descriptions))


def test_templates_have_different_system_prompts():
    """Test that templates have distinct system prompts."""
    prompts = [t.system_prompt for t in TEMPLATES.values()]
    assert len(prompts) == len(set(prompts))


def test_all_templates_have_guidelines():
    """Test that all templates include Guidelines section."""
    for template in TEMPLATES.values():
        assert "Guidelines:" in template.system_prompt


def test_reflective_vs_analytical_tone():
    """Test that reflective and analytical have different tones."""
    reflective_keywords = ["personal", "reflect", "empathetic"]
    analytical_keywords = ["critical", "evaluate", "rigor"]

    reflective_text = REFLECTIVE_TEMPLATE.system_prompt.lower()
    analytical_text = ANALYTICAL_TEMPLATE.system_prompt.lower()

    # Reflective should mention personal/empathetic
    assert any(kw in reflective_text for kw in reflective_keywords)

    # Analytical should mention critical/rigorous
    assert any(kw in analytical_text for kw in analytical_keywords)


def test_creative_higher_temperature():
    """Test that creative template has higher temperature."""
    assert CREATIVE_TEMPLATE.temperature > REFLECTIVE_TEMPLATE.temperature
    assert CREATIVE_TEMPLATE.temperature > ANALYTICAL_TEMPLATE.temperature


def test_all_templates_same_target_questions():
    """Test that all templates target same number of questions."""
    targets = [t.target_questions for t in TEMPLATES.values()]
    assert len(set(targets)) == 1  # All the same
    assert targets[0] == 5


def test_all_templates_same_max_depth():
    """Test that all templates have same max depth."""
    depths = [t.max_depth for t in TEMPLATES.values()]
    assert len(set(depths)) == 1  # All the same
    assert depths[0] == 3


# Prompt Content Quality Tests


def test_reflective_initial_prompt_mentions_episode():
    """Test that reflective initial prompt references episode content."""
    prompt = REFLECTIVE_TEMPLATE.initial_question_prompt.lower()
    assert "episode" in prompt


def test_analytical_initial_prompt_mentions_evaluation():
    """Test that analytical initial prompt mentions evaluation."""
    prompt = ANALYTICAL_TEMPLATE.initial_question_prompt.lower()
    assert "evaluate" in prompt or "critically" in prompt


def test_creative_initial_prompt_mentions_connection():
    """Test that creative initial prompt mentions making connections."""
    prompt = CREATIVE_TEMPLATE.initial_question_prompt.lower()
    assert "connection" in prompt


def test_follow_up_prompts_mention_deeper():
    """Test that follow-up prompts encourage deeper exploration."""
    for template in TEMPLATES.values():
        prompt = template.follow_up_prompt.lower()
        assert (
            "deeper" in prompt
            or "further" in prompt
            or "more" in prompt
            or "explore" in prompt
            or "challenges" in prompt  # Analytical template uses this
            or "alternative" in prompt  # Also analytical approach
        )


def test_conclusion_prompts_mention_action_or_change():
    """Test that conclusion prompts ask about action or change."""
    reflective_conclusion = REFLECTIVE_TEMPLATE.conclusion_prompt.lower()
    analytical_conclusion = ANALYTICAL_TEMPLATE.conclusion_prompt.lower()
    creative_conclusion = CREATIVE_TEMPLATE.conclusion_prompt.lower()

    assert "action" in reflective_conclusion or "next steps" in reflective_conclusion
    assert "changes" in analytical_conclusion or "view" in analytical_conclusion
    assert "application" in creative_conclusion or "project" in creative_conclusion

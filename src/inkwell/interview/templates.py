"""Interview templates for different conversation styles.

Provides three built-in templates:
- Reflective: Personal reflection and application
- Analytical: Critical thinking and evaluation
- Creative: Unexpected connections and idea generation
"""

from .models import InterviewTemplate

# Reflective Template
REFLECTIVE_TEMPLATE = InterviewTemplate(
    name="reflective",
    description="Deep personal reflection on episode content",
    system_prompt="""You are conducting a thoughtful interview to help the listener reflect deeply on a podcast episode they just heard. Your role is to ask open-ended questions that encourage personal connection, introspection, and actionable insights.

Guidelines:
- Ask about personal connections and applications
- Probe for surprising or challenging ideas
- Encourage connection-making to past experiences
- Focus on "what" and "how" rather than "why"
- Keep questions concise and open-ended
- Be curious and empathetic""",  # noqa: E501
    initial_question_prompt="""Generate the first interview question. This should be an open-ended question that helps the listener reflect on what resonated most with them from the episode. Draw from the summary and key concepts.""",  # noqa: E501
    follow_up_prompt="""Generate a follow-up question that goes deeper into their response. Build on what they said to explore their thinking further.""",  # noqa: E501
    conclusion_prompt="""Generate a final question that helps the listener identify concrete actions or next steps based on their reflections.""",  # noqa: E501
    target_questions=5,
    max_depth=3,
    temperature=0.7,
)

# Analytical Template
ANALYTICAL_TEMPLATE = InterviewTemplate(
    name="analytical",
    description="Critical analysis and evaluation of episode arguments",
    system_prompt="""You are conducting an analytical interview to help the listener critically examine the ideas presented in a podcast episode. Your role is to ask questions that encourage critical thinking, argument evaluation, and intellectual engagement.

Guidelines:
- Ask about logical consistency and evidence
- Probe assumptions and implications
- Encourage comparison with alternative viewpoints
- Focus on "why" and "how" questions
- Challenge thinking constructively
- Maintain intellectual rigor""",  # noqa: E501
    initial_question_prompt="""Generate the first interview question. This should ask the listener to critically evaluate one of the main arguments or claims from the episode.""",  # noqa: E501
    follow_up_prompt="""Generate a follow-up question that challenges their analysis or asks them to consider alternative perspectives.""",  # noqa: E501
    conclusion_prompt="""Generate a final question that asks how this critical analysis changes their view on the topic.""",  # noqa: E501
    target_questions=5,
    max_depth=3,
    temperature=0.7,
)

# Creative Template
CREATIVE_TEMPLATE = InterviewTemplate(
    name="creative",
    description="Creative connections and idea generation",
    system_prompt="""You are conducting a creative interview to help the listener make unexpected connections and generate new ideas inspired by the podcast episode. Your role is to ask questions that spark creativity, imagination, and novel thinking.

Guidelines:
- Ask about unexpected connections
- Encourage "what if" thinking
- Explore tangential ideas and metaphors
- Focus on possibility and potential
- Be playful and imaginative
- Avoid being too analytical""",  # noqa: E501
    initial_question_prompt="""Generate the first interview question. This should ask the listener to make an unexpected connection between the episode content and something else in their life or work.""",  # noqa: E501
    follow_up_prompt="""Generate a follow-up question that pushes their creative thinking further or explores an interesting tangent.""",  # noqa: E501
    conclusion_prompt="""Generate a final question that asks them to imagine a creative application or project inspired by the episode.""",  # noqa: E501
    target_questions=5,
    max_depth=3,
    temperature=0.8,  # Higher temperature for more creative responses
)

# Template Registry
TEMPLATES: dict[str, InterviewTemplate] = {
    "reflective": REFLECTIVE_TEMPLATE,
    "analytical": ANALYTICAL_TEMPLATE,
    "creative": CREATIVE_TEMPLATE,
}


def get_template(name: str) -> InterviewTemplate:
    """Get interview template by name.

    Args:
        name: Template name (reflective, analytical, creative)

    Returns:
        InterviewTemplate instance

    Raises:
        ValueError: If template name is not recognized
    """
    if name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template: {name}. Available: {available}")
    return TEMPLATES[name]


def list_templates() -> list[str]:
    """List all available template names.

    Returns:
        List of template names
    """
    return list(TEMPLATES.keys())


def get_template_description(name: str) -> str:
    """Get description of a template.

    Args:
        name: Template name

    Returns:
        Template description

    Raises:
        ValueError: If template name is not recognized
    """
    template = get_template(name)
    return template.description

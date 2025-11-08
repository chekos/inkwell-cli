"""Interview mode for Inkwell - conversational reflection on podcast episodes."""

from inkwell.interview.agent import InterviewAgent
from inkwell.interview.context_builder import InterviewContextBuilder
from inkwell.interview.models import (
    Exchange,
    InterviewContext,
    InterviewGuidelines,
    InterviewResult,
    InterviewSession,
    InterviewTemplate,
    Question,
    Response,
)
from inkwell.interview.session_manager import SessionManager
from inkwell.interview.templates import (
    get_template,
    get_template_description,
    list_templates,
)

__all__ = [
    "Exchange",
    "InterviewAgent",
    "InterviewContext",
    "InterviewContextBuilder",
    "InterviewGuidelines",
    "InterviewResult",
    "InterviewSession",
    "InterviewTemplate",
    "Question",
    "Response",
    "SessionManager",
    "get_template",
    "get_template_description",
    "list_templates",
]

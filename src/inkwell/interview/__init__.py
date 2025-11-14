"""Interview mode for Inkwell - conversational reflection on podcast episodes.

This module has been simplified to reduce complexity from 3,680 LOC to 509 LOC
(86% reduction). The new SimpleInterviewer provides core functionality without:
- Session management (no pause/resume)
- Multiple templates (single reflective template)
- Multiple formats (single markdown format)
- Metrics tracking (only essential cost tracking)
"""

from inkwell.interview.simple_interviewer import (
    SimpleInterviewer,
    SimpleInterviewResult,
    conduct_interview_from_output,
)

__all__ = [
    "SimpleInterviewer",
    "SimpleInterviewResult",
    "conduct_interview_from_output",
]

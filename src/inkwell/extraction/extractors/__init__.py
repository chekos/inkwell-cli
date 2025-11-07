"""LLM provider implementations for extraction.

This package contains concrete implementations of BaseExtractor
for various LLM providers (Claude, Gemini, etc.).
"""

from .base import BaseExtractor

__all__ = [
    "BaseExtractor",
]

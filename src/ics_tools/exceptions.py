"""Exception classes for ics-tools."""

from __future__ import annotations


class ICSError(Exception):
    """Base exception for all ics-tools errors."""


class ParseError(ICSError):
    """Raised when an iCalendar stream cannot be parsed."""

    def __init__(self, message: str, line_number: int | None = None, line_content: str | None = None) -> None:
        self.line_number = line_number
        self.line_content = line_content
        full_message = message
        if line_number is not None:
            full_message = f"Line {line_number}: {message}"
        if line_content is not None:
            full_message = f"{full_message} (content: {line_content!r})"
        super().__init__(full_message)


class ValidationError(ICSError):
    """Raised when an iCalendar object violates RFC 5545 requirements."""

    def __init__(self, message: str, component: str | None = None, property_name: str | None = None) -> None:
        self.component = component
        self.property_name = property_name
        super().__init__(message)


class RRuleError(ICSError):
    """Raised when an RRULE recurrence definition is invalid or cannot be expanded."""


class TimezoneError(ICSError):
    """Raised when a timezone cannot be parsed or resolved."""

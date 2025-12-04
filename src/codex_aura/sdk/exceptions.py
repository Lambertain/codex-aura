"""Custom exceptions for Codex Aura SDK."""


class CodexAuraError(Exception):
    """Base exception for Codex Aura SDK errors."""
    pass


class ConnectionError(CodexAuraError):
    """Raised when connection to server fails."""
    pass


class AnalysisError(CodexAuraError):
    """Raised when analysis operation fails."""
    pass


class ValidationError(CodexAuraError):
    """Raised when input validation fails."""
    pass


class TimeoutError(CodexAuraError):
    """Raised when operation times out."""
    pass
"""Typed failures raised at trust boundaries."""


class VerilogAgentError(Exception):
    """Base exception for expected harness failures."""


class SpecValidationError(VerilogAgentError):
    """The input specification is invalid or unsafe."""


class WorkspaceError(VerilogAgentError):
    """A requested path is outside the repository or cannot be prepared."""


class InfrastructureError(VerilogAgentError):
    """A required executable or process facility is unavailable."""


class ModelClientError(VerilogAgentError):
    """A model client is unavailable or returned no usable response."""


class InvalidModelOutputError(VerilogAgentError):
    """Model output violates the single-DUT contract."""

"""Shared typed records for simulation, diagnostics, and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DiagnosticKind(StrEnum):
    COMPILE_ERROR = "COMPILE_ERROR"
    SIMULATION_ERROR = "SIMULATION_ERROR"
    ASSERTION_FAILURE = "ASSERTION_FAILURE"
    TIMEOUT = "TIMEOUT"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    INVALID_SPEC = "INVALID_SPEC"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FinalStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    INVALID_SPEC = "INVALID_SPEC"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    launch_error: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    kind: DiagnosticKind
    message: str
    attempt: int
    file: str | None = None
    line: int | None = None
    vector: str | None = None
    expected: str | None = None
    actual: str | None = None
    raw_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "message": self.message,
            "attempt": self.attempt,
            "file": self.file,
            "line": self.line,
            "vector": self.vector,
            "expected": self.expected,
            "actual": self.actual,
            "raw_excerpt": self.raw_excerpt,
        }


@dataclass
class AttemptRecord:
    attempt: int
    rtl_path: str
    rtl_sha256: str
    model_response_sha256: str
    compile_command: list[str] = field(default_factory=list)
    compile_exit_code: int | None = None
    simulation_command: list[str] = field(default_factory=list)
    simulation_exit_code: int | None = None
    diagnostic: Diagnostic | None = None
    duration_seconds: float = 0.0
    log_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "rtl_path": self.rtl_path,
            "rtl_sha256": self.rtl_sha256,
            "model_response_sha256": self.model_response_sha256,
            "compile_command": self.compile_command,
            "compile_exit_code": self.compile_exit_code,
            "simulation_command": self.simulation_command,
            "simulation_exit_code": self.simulation_exit_code,
            "diagnostic": self.diagnostic.to_dict() if self.diagnostic else None,
            "duration_seconds": self.duration_seconds,
            "log_truncated": self.log_truncated,
        }

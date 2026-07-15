from __future__ import annotations

from verilog_agent.diagnostics import parse_compile_failure, parse_simulation_failure
from verilog_agent.models import CommandResult, DiagnosticKind


def _result(
    *,
    exit_code: int | None = 1,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        argv=("tool",),
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.1,
        timed_out=timed_out,
    )


def test_parses_compile_file_line_and_message() -> None:
    diagnostic = parse_compile_failure(
        _result(stderr="dut_attempt_01.v:7: syntax error"), 1
    )
    assert diagnostic.kind is DiagnosticKind.COMPILE_ERROR
    assert diagnostic.file == "dut_attempt_01.v"
    assert diagnostic.line == 7
    assert diagnostic.message == "syntax error"


def test_parses_assertion_vector_expected_and_actual() -> None:
    diagnostic = parse_simulation_failure(
        _result(
            stdout=(
                "VVA_VERIFICATION_FAIL vector=alu_1_2_1 "
                "expected=f/0/0 actual=3/0/0"
            )
        ),
        2,
    )
    assert diagnostic.kind is DiagnosticKind.ASSERTION_FAILURE
    assert diagnostic.vector == "alu_1_2_1"
    assert diagnostic.expected == "f/0/0"
    assert diagnostic.actual == "3/0/0"
    assert diagnostic.attempt == 2


def test_classifies_simulation_error_without_sentinel() -> None:
    diagnostic = parse_simulation_failure(_result(stderr="runtime error"), 1)
    assert diagnostic.kind is DiagnosticKind.SIMULATION_ERROR


def test_classifies_timeout() -> None:
    diagnostic = parse_simulation_failure(
        _result(exit_code=None, timed_out=True), 3
    )
    assert diagnostic.kind is DiagnosticKind.TIMEOUT

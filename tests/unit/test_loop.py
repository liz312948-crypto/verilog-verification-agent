from __future__ import annotations

from pathlib import Path

from tests.conftest import build_spec
from verilog_agent.errors import InfrastructureError
from verilog_agent.loop import VerificationLoop
from verilog_agent.model_client import ScriptedModelClient
from verilog_agent.models import CommandResult, DiagnosticKind, FinalStatus
from verilog_agent.spec import CircuitKind

BUGGY = """
module mux2(input wire a, input wire b, input wire sel, output wire y);
  assign y = sel ? a : b; // BUG
endmodule
"""
GOOD = """
module mux2(input wire a, input wire b, input wire sel, output wire y);
  assign y = sel ? b : a;
endmodule
"""


class DeterministicFakeSimulator:
    available = True

    def ensure_available(self) -> None:
        return None

    def tool_versions(self, cwd: Path) -> dict[str, str | None]:
        del cwd
        return {"iverilog_version": "fake", "vvp_version": "fake"}

    def compile(
        self, dut_path: Path, testbench_path: Path, *, workdir: Path, attempt: int
    ) -> tuple[CommandResult, Path]:
        del testbench_path
        source = dut_path.read_text(encoding="utf-8")
        artifact = workdir / f"simulation_attempt_{attempt:02d}.vvp"
        artifact.write_text(source, encoding="utf-8")
        failed = "SYNTAX_ERROR" in source
        return (
            CommandResult(
                argv=("iverilog", "-g2012", dut_path.name),
                exit_code=1 if failed else 0,
                stdout="",
                stderr="dut_attempt_01.v:2: syntax error" if failed else "",
                duration_seconds=0.01,
            ),
            artifact,
        )

    def run(self, artifact: Path, *, workdir: Path) -> CommandResult:
        del workdir
        failed = "BUG" in artifact.read_text(encoding="utf-8")
        return CommandResult(
            argv=("vvp", artifact.name),
            exit_code=1 if failed else 0,
            stdout=(
                "VVA_VERIFICATION_FAIL vector=mux_100 expected=1 actual=0"
                if failed
                else "VVA_VERIFICATION_PASS"
            ),
            stderr="",
            duration_seconds=0.01,
        )


class MissingSimulator(DeterministicFakeSimulator):
    available = False

    def ensure_available(self) -> None:
        raise InfrastructureError("required executable(s) not found")


def _output(repository_root: Path, tmp_path: Path, name: str) -> str:
    return (tmp_path / name).relative_to(repository_root).as_posix()


def test_first_failure_then_repair_success(
    repository_root: Path, tmp_path: Path
) -> None:
    client = ScriptedModelClient([BUGGY, GOOD])
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=DeterministicFakeSimulator(),  # type: ignore[arg-type]
    ).run(build_spec(CircuitKind.MUX2), _output(repository_root, tmp_path, "success"))
    assert report.final_status is FinalStatus.PASSED
    assert report.total_attempts == 2
    assert report.repair_retries_used == 1
    assert report.attempts[0].diagnostic is not None
    assert report.attempts[0].diagnostic.kind is DiagnosticKind.ASSERTION_FAILURE
    assert (tmp_path / "success" / "attempt_01_simulation_stdout.txt").is_file()


def test_exhaustion_is_strictly_bounded_to_four_attempts(
    repository_root: Path, tmp_path: Path
) -> None:
    client = ScriptedModelClient([BUGGY] * 4)
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=DeterministicFakeSimulator(),  # type: ignore[arg-type]
    ).run(build_spec(retries=3), _output(repository_root, tmp_path, "exhausted"))
    assert report.final_status is FinalStatus.FAILED
    assert report.total_attempts == 4
    assert report.repair_retries_used == 3
    assert len(client.calls) == 4


def test_missing_tools_do_not_call_model_or_retry(
    repository_root: Path, tmp_path: Path
) -> None:
    client = ScriptedModelClient([GOOD])
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=MissingSimulator(),  # type: ignore[arg-type]
    ).run(build_spec(), _output(repository_root, tmp_path, "missing"))
    assert report.final_status is FinalStatus.INFRASTRUCTURE_ERROR
    assert report.total_attempts == 0
    assert report.repair_retries_used == 0
    assert client.calls == []

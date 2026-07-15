from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import build_spec
from verilog_agent.diagnostics import parse_compile_failure, parse_simulation_failure
from verilog_agent.models import DiagnosticKind
from verilog_agent.simulator import Simulator
from verilog_agent.spec import CircuitKind
from verilog_agent.testbench import PASS_SENTINEL, generate_testbench

pytestmark = pytest.mark.integration


@pytest.fixture
def simulator() -> Simulator:
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        pytest.skip("local Icarus Verilog tools are not installed")
    return Simulator()


def _stage(
    repository_root: Path, tmp_path: Path, kind: CircuitKind, group: str
) -> tuple[Path, Path]:
    dut = tmp_path / "dut.v"
    tb = tmp_path / "tb.v"
    source_name = (
        f"{kind.value}.v" if group == "correct" else f"{kind.value}_buggy.v"
    )
    dut.write_text(
        (repository_root / "examples" / group / source_name).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    tb.write_text(generate_testbench(build_spec(kind)), encoding="utf-8")
    return dut, tb


@pytest.mark.parametrize("kind", list(CircuitKind))
def test_all_correct_examples_compile_and_simulate(
    simulator: Simulator,
    repository_root: Path,
    tmp_path: Path,
    kind: CircuitKind,
) -> None:
    dut, tb = _stage(repository_root, tmp_path, kind, "correct")
    compile_result, artifact = simulator.compile(dut, tb, workdir=tmp_path, attempt=1)
    assert compile_result.exit_code == 0, compile_result.stderr
    simulation_result = simulator.run(artifact, workdir=tmp_path)
    assert simulation_result.exit_code == 0, simulation_result.stderr
    assert simulation_result.stdout.count(PASS_SENTINEL) == 1


@pytest.mark.parametrize("kind", list(CircuitKind))
def test_all_buggy_examples_are_rejected_by_trusted_testbench(
    simulator: Simulator,
    repository_root: Path,
    tmp_path: Path,
    kind: CircuitKind,
) -> None:
    dut, tb = _stage(repository_root, tmp_path, kind, "broken")
    compile_result, artifact = simulator.compile(dut, tb, workdir=tmp_path, attempt=1)
    assert compile_result.exit_code == 0, compile_result.stderr
    simulation_result = simulator.run(artifact, workdir=tmp_path)
    diagnostic = parse_simulation_failure(simulation_result, 1)
    assert simulation_result.exit_code != 0
    assert diagnostic.kind is DiagnosticKind.ASSERTION_FAILURE


def test_syntax_error_is_compile_error(
    simulator: Simulator, tmp_path: Path
) -> None:
    dut = tmp_path / "dut.v"
    tb = tmp_path / "tb.v"
    dut.write_text("module mux2( this is not valid endmodule\n", encoding="utf-8")
    tb.write_text(generate_testbench(build_spec()), encoding="utf-8")
    result, _ = simulator.compile(dut, tb, workdir=tmp_path, attempt=1)
    diagnostic = parse_compile_failure(result, 1)
    assert result.exit_code != 0
    assert diagnostic.kind is DiagnosticKind.COMPILE_ERROR


def test_nonterminating_simulation_is_killed(
    simulator: Simulator, tmp_path: Path
) -> None:
    simulator.simulation_timeout_seconds = 0.2
    dut = tmp_path / "dut.v"
    tb = tmp_path / "tb.v"
    dut.write_text("module harmless; endmodule\n", encoding="utf-8")
    tb.write_text(
        "module tb; initial begin while (1) #1; end endmodule\n",
        encoding="utf-8",
    )
    compile_result, artifact = simulator.compile(dut, tb, workdir=tmp_path, attempt=1)
    assert compile_result.exit_code == 0, compile_result.stderr
    result = simulator.run(artifact, workdir=tmp_path)
    assert result.timed_out
    assert result.exit_code is None

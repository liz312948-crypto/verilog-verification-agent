from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import build_spec
from verilog_agent.loop import VerificationLoop
from verilog_agent.model_client import ScriptedModelClient
from verilog_agent.models import DiagnosticKind, FinalStatus
from verilog_agent.simulator import Simulator
from verilog_agent.spec import CircuitKind, Mode

pytestmark = pytest.mark.e2e


@pytest.fixture
def simulator() -> Simulator:
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        pytest.skip("local Icarus Verilog tools are not installed")
    return Simulator()


def _example(root: Path, kind: CircuitKind, group: str) -> str:
    filename = f"{kind.value}.v" if group == "correct" else f"{kind.value}_buggy.v"
    return (root / "examples" / group / filename).read_text(encoding="utf-8")


def _output(root: Path, tmp_path: Path, name: str) -> str:
    return (tmp_path / name).relative_to(root).as_posix()


@pytest.mark.parametrize("kind", list(CircuitKind))
def test_generate_verifies_all_seven_correct_circuits(
    simulator: Simulator,
    repository_root: Path,
    tmp_path: Path,
    kind: CircuitKind,
) -> None:
    client = ScriptedModelClient([_example(repository_root, kind, "correct")])
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=simulator,
    ).run(build_spec(kind), _output(repository_root, tmp_path, f"correct-{kind.value}"))
    assert report.final_status is FinalStatus.PASSED
    assert report.total_attempts == 1
    assert report.repair_retries_used == 0
    run_dir = tmp_path / f"correct-{kind.value}"
    assert (run_dir / "compile_stdout.txt").is_file()
    assert (run_dir / "compile_stderr.txt").is_file()
    assert (run_dir / "simulation_stdout.txt").is_file()
    assert (run_dir / "simulation_stderr.txt").is_file()


@pytest.mark.parametrize("kind", list(CircuitKind))
def test_each_buggy_circuit_fails_then_scripted_repair_succeeds(
    simulator: Simulator,
    repository_root: Path,
    tmp_path: Path,
    kind: CircuitKind,
) -> None:
    client = ScriptedModelClient(
        [
            _example(repository_root, kind, "broken"),
            _example(repository_root, kind, "correct"),
        ]
    )
    output_name = f"repair-{kind.value}"
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=simulator,
    ).run(build_spec(kind), _output(repository_root, tmp_path, output_name))
    assert report.final_status is FinalStatus.PASSED
    assert report.total_attempts == 2
    assert report.repair_retries_used == 1
    assert report.attempts[0].diagnostic is not None
    assert report.attempts[0].diagnostic.kind is DiagnosticKind.ASSERTION_FAILURE
    data = json.loads(
        (tmp_path / output_name / "report.json").read_text(encoding="utf-8")
    )
    assert len(data["attempts"]) == 2
    assert data["final_rtl_path"] == "final_dut.v"


def test_three_repairs_are_exhausted_after_exactly_four_attempts(
    simulator: Simulator, repository_root: Path, tmp_path: Path
) -> None:
    broken = _example(repository_root, CircuitKind.MUX2, "broken")
    client = ScriptedModelClient([broken] * 4)
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=simulator,
    ).run(build_spec(retries=3), _output(repository_root, tmp_path, "exhaustion"))
    assert report.final_status is FinalStatus.FAILED
    assert report.total_attempts == 4
    assert report.repair_retries_used == 3
    assert len(list((tmp_path / "exhaustion").glob("dut_attempt_*.v"))) == 4


def test_repair_mode_loads_existing_rtl_then_repairs(
    simulator: Simulator, repository_root: Path, tmp_path: Path
) -> None:
    spec = build_spec(
        CircuitKind.COUNTER4,
        mode=Mode.REPAIR,
        rtl_path="examples/broken/counter4_buggy.v",
    )
    client = ScriptedModelClient(
        [_example(repository_root, CircuitKind.COUNTER4, "correct")]
    )
    report = VerificationLoop(
        repository_root=repository_root,
        model_client=client,
        simulator=simulator,
    ).run(spec, _output(repository_root, tmp_path, "repair-mode"))
    assert report.final_status is FinalStatus.PASSED
    assert client.calls == ["repair"]
    assert report.total_attempts == 2


def test_cli_success_and_failure_exit_codes(
    simulator: Simulator, repository_root: Path, tmp_path: Path
) -> None:
    environment = os.environ.copy()
    assert simulator.iverilog is not None
    assert simulator.vvp is not None
    environment["VVA_IVERILOG"] = simulator.iverilog
    environment["VVA_VVP"] = simulator.vvp
    success_output = _output(repository_root, tmp_path, "cli-success")
    success = subprocess.run(
        [
            sys.executable,
            "-m",
            "verilog_agent",
            "generate",
            "--spec",
            "examples/specs/mux2.json",
            "--output",
            success_output,
            "--scripted-response",
            "examples/correct/mux2.v",
        ],
        cwd=repository_root,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )
    assert success.returncode == 0, success.stderr

    failure_output = _output(repository_root, tmp_path, "cli-failure")
    failure = subprocess.run(
        [
            sys.executable,
            "-m",
            "verilog_agent",
            "generate",
            "--spec",
            "examples/specs/mux2.json",
            "--output",
            failure_output,
            "--scripted-response",
            "examples/broken/mux2_buggy.v",
        ],
        cwd=repository_root,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )
    assert failure.returncode == 1
    assert (repository_root / failure_output / "report.json").is_file()

    repair_output = _output(repository_root, tmp_path, "cli-repair")
    repair = subprocess.run(
        [
            sys.executable,
            "-m",
            "verilog_agent",
            "repair",
            "--spec",
            "examples/specs/counter4.json",
            "--rtl",
            "examples/broken/counter4_buggy.v",
            "--output",
            repair_output,
            "--scripted-response",
            "examples/correct/counter4.v",
        ],
        cwd=repository_root,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )
    assert repair.returncode == 0, repair.stderr
    repair_data = json.loads(
        (repository_root / repair_output / "report.json").read_text(encoding="utf-8")
    )
    assert repair_data["mode"] == "repair"
    assert repair_data["total_attempts"] == 2

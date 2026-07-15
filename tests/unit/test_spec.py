from __future__ import annotations

import json
from pathlib import Path

import pytest

from verilog_agent.errors import SpecValidationError
from verilog_agent.spec import CircuitKind, Mode, TaskSpec, load_spec


def _write_spec(root: Path, directory: Path, updates: dict[str, object]) -> str:
    data: dict[str, object] = {
        "schema_version": "1.0",
        "task_name": "valid_task",
        "mode": "generate",
        "circuit_kind": "mux2",
        "module_name": "mux2",
        "description": "valid",
        "max_repair_retries": 3,
    }
    data.update(updates)
    path = directory / "spec.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path.resolve().relative_to(root.resolve()).as_posix()


def test_load_valid_spec(repository_root: Path, tmp_path: Path) -> None:
    path = _write_spec(repository_root, tmp_path, {})
    spec = load_spec(path, repository_root)
    assert spec.circuit_kind is CircuitKind.MUX2
    assert spec.mode is Mode.GENERATE
    assert len(spec.spec_sha256) == 64
    assert spec.max_attempts == 4


@pytest.mark.parametrize(
    "module_name", ["2mux", "bad-name", "bad name", "a/b", "module", "always"]
)
def test_rejects_illegal_module_names(
    repository_root: Path, tmp_path: Path, module_name: str
) -> None:
    path = _write_spec(repository_root, tmp_path, {"module_name": module_name})
    with pytest.raises(SpecValidationError, match="module_name"):
        load_spec(path, repository_root)


def test_rejects_unknown_circuit_kind(repository_root: Path, tmp_path: Path) -> None:
    path = _write_spec(repository_root, tmp_path, {"circuit_kind": "cpu"})
    with pytest.raises(SpecValidationError, match="circuit_kind"):
        load_spec(path, repository_root)


def test_rejects_unknown_fields(repository_root: Path, tmp_path: Path) -> None:
    path = _write_spec(repository_root, tmp_path, {"surprise": True})
    with pytest.raises(SpecValidationError, match="unknown field"):
        load_spec(path, repository_root)


def test_rejects_path_traversal(repository_root: Path) -> None:
    with pytest.raises(SpecValidationError, match="path traversal"):
        load_spec("../outside.json", repository_root)


@pytest.mark.parametrize("retries", [-1, 4, True, "3"])
def test_rejects_invalid_retry_count(
    repository_root: Path, tmp_path: Path, retries: object
) -> None:
    path = _write_spec(
        repository_root, tmp_path, {"max_repair_retries": retries}
    )
    with pytest.raises(SpecValidationError, match="max_repair_retries"):
        load_spec(path, repository_root)


def test_repair_requires_repository_relative_rtl(
    repository_root: Path, tmp_path: Path
) -> None:
    path = _write_spec(repository_root, tmp_path, {"mode": "repair"})
    with pytest.raises(SpecValidationError, match="rtl_path"):
        load_spec(path, repository_root)


def test_mode_must_match_command(repository_root: Path, tmp_path: Path) -> None:
    path = _write_spec(repository_root, tmp_path, {})
    with pytest.raises(SpecValidationError, match="command requires"):
        load_spec(path, repository_root, expected_mode=Mode.REPAIR)


def test_direct_task_spec_cannot_bypass_retry_ceiling() -> None:
    with pytest.raises(SpecValidationError, match="between 0 and 3"):
        TaskSpec(
            schema_version="1.0",
            task_name="direct",
            mode=Mode.GENERATE,
            circuit_kind=CircuitKind.MUX2,
            module_name="mux2",
            description="direct",
            max_repair_retries=4,
            spec_sha256="a" * 64,
        )


def test_rejects_oversized_specification(repository_root: Path, tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    path.write_text(" " * (64 * 1024 + 1), encoding="utf-8")
    relative = path.relative_to(repository_root).as_posix()
    with pytest.raises(SpecValidationError, match="exceeds"):
        load_spec(relative, repository_root)

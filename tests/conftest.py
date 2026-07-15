from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from verilog_agent.spec import CircuitKind, Mode, TaskSpec

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del session, exitstatus
    shutil.rmtree(REPOSITORY_ROOT / ".pytest-tmp", ignore_errors=True)


@pytest.fixture
def repository_root() -> Path:
    return REPOSITORY_ROOT


def build_spec(
    kind: CircuitKind = CircuitKind.MUX2,
    *,
    mode: Mode = Mode.GENERATE,
    retries: int = 3,
    rtl_path: str | None = None,
    task_name: str | None = None,
) -> TaskSpec:
    return TaskSpec(
        schema_version="1.0",
        task_name=task_name or f"{kind.value}_test",
        mode=mode,
        circuit_kind=kind,
        module_name=kind.value,
        description=f"Test specification for {kind.value}",
        max_repair_retries=retries,
        spec_sha256="a" * 64,
        rtl_path=rtl_path,
    )

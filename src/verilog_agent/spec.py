"""Strict JSON specification model and parser."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from verilog_agent.errors import SpecValidationError, WorkspaceError
from verilog_agent.workspace import resolve_repository_path

MAX_SPEC_BYTES = 64 * 1024
MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
TASK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
VERILOG_RESERVED_WORDS = {
    "always",
    "assign",
    "begin",
    "case",
    "end",
    "endcase",
    "endmodule",
    "function",
    "generate",
    "if",
    "inout",
    "input",
    "module",
    "output",
    "reg",
    "task",
    "wire",
}
KNOWN_FIELDS = {
    "schema_version",
    "task_name",
    "mode",
    "circuit_kind",
    "module_name",
    "description",
    "max_repair_retries",
    "rtl_path",
}


class CircuitKind(StrEnum):
    MUX2 = "mux2"
    ADDER4 = "adder4"
    COUNTER4 = "counter4"
    SHIFT_REGISTER4 = "shift_register4"
    RISING_EDGE_DETECTOR = "rising_edge_detector"
    SEQUENCE_DETECTOR_1011 = "sequence_detector_1011"
    ALU4 = "alu4"


class Mode(StrEnum):
    GENERATE = "generate"
    REPAIR = "repair"


@dataclass(frozen=True)
class TaskSpec:
    schema_version: str
    task_name: str
    mode: Mode
    circuit_kind: CircuitKind
    module_name: str
    description: str
    max_repair_retries: int
    spec_sha256: str
    rtl_path: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise SpecValidationError("schema_version: only '1.0' is supported")
        if not TASK_NAME_RE.fullmatch(self.task_name):
            raise SpecValidationError("task_name: invalid task identifier")
        if not isinstance(self.mode, Mode):
            raise SpecValidationError("mode: expected a Mode value")
        if not isinstance(self.circuit_kind, CircuitKind):
            raise SpecValidationError("circuit_kind: expected a CircuitKind value")
        if (
            not MODULE_NAME_RE.fullmatch(self.module_name)
            or self.module_name.lower() in VERILOG_RESERVED_WORDS
        ):
            raise SpecValidationError("module_name: invalid Verilog identifier")
        if isinstance(self.max_repair_retries, bool) or not isinstance(
            self.max_repair_retries, int
        ):
            raise SpecValidationError("max_repair_retries: expected an integer from 0 through 3")
        if not 0 <= self.max_repair_retries <= 3:
            raise SpecValidationError("max_repair_retries: must be between 0 and 3")

    @property
    def max_attempts(self) -> int:
        return 1 + self.max_repair_retries

    def to_dict(self, *, include_hash: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "task_name": self.task_name,
            "mode": self.mode.value,
            "circuit_kind": self.circuit_kind.value,
            "module_name": self.module_name,
            "description": self.description,
            "max_repair_retries": self.max_repair_retries,
        }
        if self.rtl_path is not None:
            result["rtl_path"] = self.rtl_path
        if include_hash:
            result["spec_sha256"] = self.spec_sha256
        return result


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SpecValidationError(f"{field}: expected a non-empty string")
    return value


def _parse_json(raw: bytes, path_label: str) -> dict[str, Any]:
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SpecValidationError(f"{path_label}: specification is not valid UTF-8") from exc
    try:
        value = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise SpecValidationError(
            f"{path_label}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise SpecValidationError(f"{path_label}: top-level JSON value must be an object")
    return value


def load_spec(
    spec_path: str,
    repository_root: Path,
    *,
    expected_mode: Mode | None = None,
    rtl_override: str | None = None,
) -> TaskSpec:
    """Load a repository-relative specification and enforce the complete schema."""
    try:
        path = resolve_repository_path(repository_root, spec_path, must_exist=True)
    except WorkspaceError as exc:
        raise SpecValidationError(f"spec path: {exc}") from exc
    size = path.stat().st_size
    if size > MAX_SPEC_BYTES:
        raise SpecValidationError(f"specification exceeds {MAX_SPEC_BYTES} byte limit")
    raw = path.read_bytes()
    data = _parse_json(raw, spec_path)

    unknown = sorted(set(data) - KNOWN_FIELDS)
    if unknown:
        raise SpecValidationError(f"unknown field(s): {', '.join(unknown)}")

    schema_version = _required_string(data, "schema_version")
    if schema_version != "1.0":
        raise SpecValidationError("schema_version: only '1.0' is supported")

    task_name = _required_string(data, "task_name")
    if not TASK_NAME_RE.fullmatch(task_name):
        raise SpecValidationError(
            "task_name: use 1-64 ASCII letters, digits, dot, underscore, or hyphen"
        )

    mode_value = _required_string(data, "mode")
    try:
        mode = Mode(mode_value)
    except ValueError as exc:
        raise SpecValidationError(f"mode: unsupported value {mode_value!r}") from exc
    if expected_mode is not None and mode is not expected_mode:
        raise SpecValidationError(
            f"mode: command requires {expected_mode.value!r}, got {mode.value!r}"
        )

    kind_value = _required_string(data, "circuit_kind")
    try:
        circuit_kind = CircuitKind(kind_value)
    except ValueError as exc:
        allowed = ", ".join(kind.value for kind in CircuitKind)
        raise SpecValidationError(
            f"circuit_kind: unsupported value {kind_value!r}; allowed: {allowed}"
        ) from exc

    module_name = _required_string(data, "module_name")
    if (
        not MODULE_NAME_RE.fullmatch(module_name)
        or module_name.lower() in VERILOG_RESERVED_WORDS
    ):
        raise SpecValidationError(f"module_name: invalid Verilog identifier {module_name!r}")
    if len(module_name) > 128:
        raise SpecValidationError("module_name: exceeds 128 character limit")

    description = _required_string(data, "description")
    if len(description) > 2_000:
        raise SpecValidationError("description: exceeds 2000 character limit")

    retries = data.get("max_repair_retries", 3)
    if isinstance(retries, bool) or not isinstance(retries, int):
        raise SpecValidationError("max_repair_retries: expected an integer from 0 through 3")
    if not 0 <= retries <= 3:
        raise SpecValidationError("max_repair_retries: must be between 0 and 3")

    rtl_value = rtl_override if rtl_override is not None else data.get("rtl_path")
    if mode is Mode.REPAIR:
        if not isinstance(rtl_value, str) or not rtl_value:
            raise SpecValidationError(
                "rtl_path: repair mode requires a repository-relative existing RTL file"
            )
        try:
            resolve_repository_path(repository_root, rtl_value, must_exist=True)
        except WorkspaceError as exc:
            raise SpecValidationError(f"rtl_path: {exc}") from exc
    elif rtl_value is not None:
        raise SpecValidationError("rtl_path: only valid when mode is 'repair'")

    return TaskSpec(
        schema_version=schema_version,
        task_name=task_name,
        mode=mode,
        circuit_kind=circuit_kind,
        module_name=module_name,
        description=description,
        max_repair_retries=retries,
        spec_sha256=hashlib.sha256(raw).hexdigest(),
        rtl_path=rtl_value,
    )

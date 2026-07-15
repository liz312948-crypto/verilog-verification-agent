"""Repository-confined path and run-workspace helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from verilog_agent.errors import WorkspaceError

MAX_RTL_BYTES = 256 * 1024


def resolve_repository_path(repository_root: Path, value: str, *, must_exist: bool) -> Path:
    if not value or "\x00" in value:
        raise WorkspaceError("path must be a non-empty relative path")
    candidate_value = Path(value)
    if candidate_value.is_absolute():
        raise WorkspaceError(f"absolute paths are not allowed: {value}")
    if ".." in candidate_value.parts:
        raise WorkspaceError(f"path traversal is not allowed: {value}")
    root = repository_root.resolve()
    candidate = (root / candidate_value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"path escapes repository: {value}") from exc
    if must_exist and not candidate.is_file():
        raise WorkspaceError(f"file does not exist: {value}")
    return candidate


def prepare_output_directory(repository_root: Path, value: str) -> Path:
    output = resolve_repository_path(repository_root, value, must_exist=False)
    if output.exists() and not output.is_dir():
        raise WorkspaceError(f"output path is not a directory: {value}")
    if output.exists() and any(output.iterdir()):
        raise WorkspaceError(
            f"output directory is not empty; refusing to overwrite evidence: {value}"
        )
    output.mkdir(parents=True, exist_ok=True)
    return output


def read_bounded_rtl(path: Path) -> str:
    size = path.stat().st_size
    if size > MAX_RTL_BYTES:
        raise WorkspaceError(f"RTL file exceeds {MAX_RTL_BYTES} byte limit: {path.name}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceError(f"RTL file is not valid UTF-8: {path.name}") from exc


def copy_final_rtl(source: Path, destination: Path) -> None:
    shutil.copyfile(source, destination)

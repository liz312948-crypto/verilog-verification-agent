from __future__ import annotations

from pathlib import Path

import pytest

from verilog_agent.errors import InfrastructureError, WorkspaceError
from verilog_agent.workspace import prepare_output_directory, resolve_repository_path


def test_rejects_host_absolute_path(repository_root: Path) -> None:
    with pytest.raises(WorkspaceError, match="absolute"):
        resolve_repository_path(repository_root, str(repository_root), must_exist=False)


@pytest.mark.parametrize("value", ["../file.v", r"..\file.v"])
def test_rejects_posix_and_windows_traversal(
    repository_root: Path, value: str
) -> None:
    with pytest.raises(WorkspaceError, match="traversal"):
        resolve_repository_path(repository_root, value, must_exist=False)


@pytest.mark.parametrize(
    "value, message",
    [
        (r"C:\outside\file.v", "absolute"),
        (r"C:relative.v", "drive-qualified"),
        (r"\outside\file.v", "rooted"),
        (r"\\server\share\file.v", "absolute"),
    ],
)
def test_rejects_windows_qualified_paths(
    repository_root: Path, value: str, message: str
) -> None:
    with pytest.raises(WorkspaceError, match=message):
        resolve_repository_path(repository_root, value, must_exist=False)


def test_refuses_to_overwrite_existing_evidence(
    repository_root: Path, tmp_path: Path
) -> None:
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")
    relative = tmp_path.relative_to(repository_root).as_posix()
    with pytest.raises(WorkspaceError, match="refusing to overwrite"):
        prepare_output_directory(repository_root, relative)


def test_output_creation_failure_is_infrastructure_error(
    repository_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "cannot-create"

    def fail_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        del self, args, kwargs
        raise OSError("simulated create failure")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    relative = output.relative_to(repository_root).as_posix()
    with pytest.raises(InfrastructureError, match="could not prepare output directory"):
        prepare_output_directory(repository_root, relative)

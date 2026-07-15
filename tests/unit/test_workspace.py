from __future__ import annotations

from pathlib import Path

import pytest

from verilog_agent.errors import WorkspaceError
from verilog_agent.workspace import prepare_output_directory, resolve_repository_path


def test_rejects_absolute_and_traversal_paths(repository_root: Path) -> None:
    with pytest.raises(WorkspaceError, match="absolute"):
        resolve_repository_path(repository_root, str(repository_root), must_exist=False)
    with pytest.raises(WorkspaceError, match="traversal"):
        resolve_repository_path(repository_root, "../escape", must_exist=False)


def test_refuses_to_overwrite_existing_evidence(
    repository_root: Path, tmp_path: Path
) -> None:
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")
    relative = tmp_path.relative_to(repository_root).as_posix()
    with pytest.raises(WorkspaceError, match="refusing to overwrite"):
        prepare_output_directory(repository_root, relative)

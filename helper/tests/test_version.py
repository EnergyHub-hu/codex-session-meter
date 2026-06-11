from __future__ import annotations

from pathlib import Path
import tomllib

import codex_session_widget


def test_package_version_matches_pyproject() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert codex_session_widget.__version__ == metadata["project"]["version"]

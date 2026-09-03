from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - covered by Python 3.10
    import tomli as tomllib


ROOT_DIR = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT_DIR / "helper" / "pyproject.toml"


def _read_pyproject() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def test_installer_does_not_self_upgrade_pip() -> None:
    installer = (ROOT_DIR / "install.sh").read_text(encoding="utf-8")

    assert not re.search(r"\bpip\s+install\s+--upgrade\b", installer)
    assert '"$VENV_DIR/bin/python" -m pip install "$ROOT_DIR/helper"' in installer


def test_build_requirements_are_exactly_pinned() -> None:
    requirements = _read_pyproject()["build-system"]["requires"]

    assert requirements == ["setuptools==83.0.0", "setuptools-scm==10.2.0"]
    assert all(">=" not in requirement for requirement in requirements)


def test_setuptools_scm_version_generation_remains_configured() -> None:
    pyproject = _read_pyproject()

    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["setuptools_scm"] == {
        "root": "..",
        "version_file": "codex_session_widget/_version.py",
    }


def _create_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"isolated venv creation failed:\n{result.stdout}\n{result.stderr}")
    return venv_dir / "bin" / "python"


def _installed_versions(installed_python: Path) -> tuple[str, str]:
    output = subprocess.check_output(
        [
            str(installed_python),
            "-c",
            "from codex_session_widget import __version__; "
            "from importlib.metadata import version; "
            "print(__version__); print(version('codex-session-meter'))",
        ],
        text=True,
    )
    package_version, metadata_version = output.strip().splitlines()
    return package_version, metadata_version


def test_source_package_installs_and_reports_generated_version(tmp_path: Path) -> None:
    installed_python = _create_venv(tmp_path)
    result = subprocess.run(
        [str(installed_python), "-m", "pip", "install", str(ROOT_DIR / "helper")],
        cwd=ROOT_DIR,
        env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    installed_version, metadata_version = _installed_versions(installed_python)
    assert installed_version == metadata_version
    assert installed_version != "0+unknown"


def test_installer_builds_and_installs_helper_from_source(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        ["bash", str(ROOT_DIR / "install.sh")],
        cwd=ROOT_DIR,
        env={
            **os.environ,
            "HOME": str(home),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INPUT": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    installed_python = home / ".local" / "share" / "codex-session-meter" / "venv" / "bin" / "python"
    installed_version, metadata_version = _installed_versions(installed_python)
    assert installed_version == metadata_version
    assert installed_version != "0+unknown"

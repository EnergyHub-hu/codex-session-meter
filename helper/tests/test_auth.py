from __future__ import annotations

import pytest

pytest.skip("disabled: auth tests interfere with local token state", allow_module_level=True)

import json

from codex_session_widget import auth


def test_codex_auth_summary_reports_cli_auth_file(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(json.dumps({"tokens": {"access_token": "secret"}}), encoding="utf-8")

    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)
    monkeypatch.setattr(auth.shutil, "which", lambda command: "/usr/bin/codex" if command == "codex" else None)

    summary = auth.codex_auth_summary()

    assert summary == {
        "ok": True,
        "auth_provider": "codex_cli",
        "codex_cli_available": True,
        "auth_file": "custom_codex_home/auth.json",
        "auth_file_location": "custom_codex_home",
        "auth_file_exists": True,
        "has_access_token": True,
    }
    assert str(tmp_path) not in summary["auth_file"]
    assert "access_token" not in summary
    assert "token" not in summary


def test_codex_access_token_reads_nested_and_top_level_tokens(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)

    auth_file.write_text(json.dumps({"tokens": {"access_token": "nested-token"}}), encoding="utf-8")
    assert auth.codex_access_token() == "nested-token"

    auth_file.write_text(json.dumps({"access_token": "top-level-token"}), encoding="utf-8")
    assert auth.codex_access_token() == "top-level-token"


def test_logout_does_not_remove_codex_cli_auth_file(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)

    auth.logout()

    assert auth_file.exists()

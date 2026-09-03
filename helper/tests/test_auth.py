from __future__ import annotations

import json

import pytest

from codex_session_widget import auth
from codex_session_widget import cli


def test_codex_auth_summary_reports_cli_auth_file(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(
        json.dumps({"tokens": {"access_token": "test-access-token-do-not-use"}}),
        encoding="utf-8",
    )

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


@pytest.mark.parametrize(
    "auth_data",
    [
        {"tokens": {"access_token": "nested-token"}},
        {"access_token": "top-level-token"},
    ],
)
def test_codex_has_access_token_reads_nested_and_top_level_tokens(tmp_path, monkeypatch, auth_data) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)

    auth_file.write_text(json.dumps(auth_data), encoding="utf-8")
    assert auth.codex_has_access_token() is True


@pytest.mark.parametrize(
    "auth_data",
    [
        {},
        {"tokens": {}},
        {"tokens": {"access_token": None}},
        {"tokens": {"access_token": ""}},
        {"tokens": {"access_token": " \t\n"}},
        {"access_token": None},
        {"access_token": ""},
        {"access_token": " \t\n"},
        [],
        None,
    ],
)
def test_codex_has_access_token_returns_false_without_usable_token(tmp_path, monkeypatch, auth_data) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(json.dumps(auth_data), encoding="utf-8")

    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)

    assert auth.codex_has_access_token() is False


def test_codex_has_access_token_returns_false_for_missing_or_malformed_auth_file(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)

    assert auth.codex_has_access_token() is False

    auth_file.write_text("not-json", encoding="utf-8")
    assert auth.codex_has_access_token() is False


def test_codex_has_access_token_returns_false_for_auth_file_read_error(monkeypatch) -> None:
    class UnreadableAuthFile:
        def read_text(self, *, encoding: str) -> str:
            raise OSError("permission denied")

    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", UnreadableAuthFile())

    assert auth.codex_has_access_token() is False


def test_auth_status_output_contains_boolean_without_token_value(tmp_path, monkeypatch, capsys) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text(
        json.dumps({"tokens": {"access_token": "test-access-token-do-not-use"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)
    monkeypatch.setattr(auth.shutil, "which", lambda command: "/usr/bin/codex" if command == "codex" else None)

    assert cli.main(["auth-status"]) == 0

    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["has_access_token"] is True
    assert isinstance(summary["has_access_token"], bool)
    assert "test-access-token-do-not-use" not in output
    assert not hasattr(auth, "codex_access_token")


def test_logout_does_not_remove_codex_cli_auth_file(tmp_path, monkeypatch) -> None:
    auth_file = tmp_path / ".codex" / "auth.json"
    auth_file.parent.mkdir()
    auth_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(auth, "CODEX_AUTH_FILE", auth_file)
    monkeypatch.setattr(auth, "_codex_command", lambda: None)

    auth.logout()

    assert auth_file.exists()

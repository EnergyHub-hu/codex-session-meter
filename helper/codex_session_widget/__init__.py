"""Codex session meter helper."""

try:
    from ._version import __version__
except ModuleNotFoundError as exc:
    if exc.name != f"{__package__}._version":
        raise
    __version__ = "0+unknown"

__all__ = ["__version__"]

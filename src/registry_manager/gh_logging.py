import os
import sys
from pathlib import Path

GIT_ROOT = Path(__file__).parent.parent


def is_running_in_github_actions():
    return "GITHUB_ACTIONS" in os.environ


class MyLog:
    """
    A simple logging class that adapts its output based on
    whether it's running in GitHub Actions.
    """

    warnings = 0

    def _loc(self, file: Path | None, line: int | None) -> str:
        if file and file.is_absolute():
            file = file.relative_to(GIT_ROOT)

        if is_running_in_github_actions():
            if file and line:
                return f"file={file},line={line}"
            elif file:
                return f"file={file}"
            else:
                return ""
        else:
            if file and line:
                return f"{file}:{line}"
            elif file:
                return f"{file}"
            else:
                return ""

    def _print(
        self, prefix: str, msg: str, file: Path | None = None, line: int | None = None
    ):
        location = self._loc(file, line)
        if is_running_in_github_actions():
            github_prefix = {
                "debug": "debug",
                "info": "notice",
                "warning": "warning",
                "error": "error",
                "success": "notice",
            }
            print(f"::{github_prefix.get(prefix, prefix)} {location}::{msg}")
        else:
            pretty_prefix = {
                "debug": "🐛",
                "info": "ℹ️",
                "warning": "⚠️",
                "error": "❌",
                "success": "✅",
            }
            print(f"{pretty_prefix.get(prefix, prefix)}: {location} {msg}")

    def debug(self, msg: str):
        self._print("debug", msg)

    def info(self, msg: str):
        self._print("info", msg)

    def ok(self, msg: str):
        self._print("success", msg)

    def warning(self, msg: str, file: Path | None = None, line: int | None = None):
        self.warnings += 1
        self._print("warning", msg, file, line)

    def fatal(self, msg: str, file: Path | None = None, line: int | None = None):
        self._print("error", msg, file, line)
        sys.exit(1)

# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

import os
import sys
from pathlib import Path
from typing import NoReturn

GIT_ROOT = Path(__file__).parent.parent.parent.resolve()


def is_running_in_github_actions() -> bool:
    return "GITHUB_ACTIONS" in os.environ


class Logger:
    """Minimal logger that prints locally and emits annotations on GitHub Actions."""

    def __init__(self, name: str):
        self.name = name
        self.warnings: list[str] = []

    def clear(self) -> None:
        self.warnings.clear()

    def _loc(self, file: Path | None, line: int | None, for_github: bool) -> str:
        if file and file.is_absolute():
            file = file.relative_to(GIT_ROOT)

        if for_github:
            if file and line:
                return f" file={file},line={line}"
            if file:
                return f" file={file}"
            return ""

        if file and line:
            return f" {file}:{line}"
        if file:
            return f" {file}"
        return ""

    def _print(
        self,
        prefix: str,
        msg: str,
        *,
        file: Path | None = None,
        line: int | None = None,
        stderr: bool = False,
    ) -> None:
        github_announcements = {"notice", "warning", "error"}

        if is_running_in_github_actions() and prefix in github_announcements:
            location = self._loc(file, line, for_github=True)
            msg = f"::{prefix}{location}::{self.name} {msg}"
        else:
            location = self._loc(file, line, for_github=False)
            msg = f"{prefix.upper()}:{location} {self.name} {msg}"

        print(msg, file=sys.stderr if stderr else sys.stdout)

    def debug(self, msg: str) -> None:
        self._print("debug", msg, stderr=True)

    def info(self, msg: str) -> None:
        self._print("info", msg)

    def notice(self, msg: str) -> None:
        self._print("notice", msg)

    def warning(
        self, msg: str, file: Path | None = None, line: int | None = None
    ) -> None:
        self.warnings.append(msg)
        self._print("warning", msg, file=file, line=line)

    def fatal(
        self, msg: str, file: Path | None = None, line: int | None = None
    ) -> NoReturn:
        self._print("error", msg, file=file, line=line)
        raise SystemExit(1)

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

    def _loc(self, file: Path | None, line: int | None) -> str:
        if file and file.is_absolute():
            file = file.relative_to(GIT_ROOT)

        if is_running_in_github_actions():
            if file and line:
                return f"file={file},line={line}"
            if file:
                return f"file={file}"
            return ""

        if file and line:
            return f" {file}:{line}"
        if file:
            return f" {file}"
        return ""

    def _print(
        self, prefix: str, msg: str, file: Path | None = None, line: int | None = None
    ) -> None:
        location = self._loc(file, line)
        if is_running_in_github_actions():
            github_prefix = {
                "debug": "debug",
                "info": "notice",
                "warning": "warning",
                "error": "error",
                "success": "notice",
            }
            print(f"::{github_prefix.get(prefix, prefix)}{location}::{self.name} {msg}")
            return

        pretty_prefix = {
            "debug": "DEBUG",
            "info": "INFO",
            "warning": "WARNING",
            "error": "ERROR",
            "success": "SUCCESS",
        }
        print(f"{pretty_prefix.get(prefix, prefix)}:{location} {self.name} {msg}")

    def debug(self, msg: str) -> None:
        self._print("debug", msg)

    def info(self, msg: str) -> None:
        self._print("info", msg)

    def ok(self, msg: str) -> None:
        self._print("success", msg)

    def warning(
        self, msg: str, file: Path | None = None, line: int | None = None
    ) -> None:
        self.warnings.append(msg)
        self._print("warning", msg, file, line)

    def fatal(
        self, msg: str, file: Path | None = None, line: int | None = None
    ) -> NoReturn:
        self._print("error", msg, file, line)
        raise SystemExit(1)

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

import sys
from typing import NoReturn


class Logger:
    """Minimal logger."""

    def __init__(self, name: str):
        self.name = name
        self.warnings: list[str] = []

    def clear(self) -> None:
        self.warnings.clear()

    def _print(self, prefix: str, msg: str, *, stderr: bool = False) -> None:
        print(
            f"{prefix.upper()}: {self.name} {msg}",
            file=sys.stderr if stderr else sys.stdout,
        )

    def debug(self, msg: str) -> None:
        self._print("debug", msg, stderr=True)

    def info(self, msg: str) -> None:
        self._print("info", msg)

    def notice(self, msg: str) -> None:
        self._print("notice", msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)
        self._print("warning", msg)

    def fatal(self, msg: str) -> NoReturn:
        self._print("error", msg)
        raise SystemExit(1)

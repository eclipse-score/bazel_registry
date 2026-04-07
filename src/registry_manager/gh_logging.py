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

_all_warnings_singleton: list[str] = []


class Logger:
    """Minimal logger."""

    def __init__(self, name: str):
        self.name = name

    def clear(self) -> None:
        _all_warnings_singleton.clear()

    @property
    def warnings(self) -> list[str]:
        return _all_warnings_singleton

    @classmethod
    def warning_messages(cls) -> list[str]:
        return list(_all_warnings_singleton)

    def _print(self, prefix: str, msg: str) -> None:
        print(
            f"{prefix.upper()}: {self.name} {msg}",
            file=sys.stderr,
        )

    def debug(self, msg: str) -> None:
        """Prints a debug message to stderr, prefixed with the module name."""
        self._print("debug", msg)

    def warning(self, msg: str) -> None:
        """Prints a warning message to stderr and stores it in the warnings list."""
        _all_warnings_singleton.append(msg)
        self._print("warning", msg)

    def fatal(self, msg: str) -> NoReturn:
        """Prints an error message to stderr and exits the program."""
        self._print("error", msg)
        raise SystemExit(1)

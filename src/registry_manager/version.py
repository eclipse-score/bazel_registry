# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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

import semver


class Version:
    def __init__(self, s: str) -> None:
        if not isinstance(s, str):
            raise TypeError("Version must be a string")

        self._raw = s

        try:
            self._semver = semver.Version.parse(s)
        except ValueError:
            self._semver = None

    @property
    def semver(self) -> semver.Version | None:
        return self._semver

    def __lt__(self, other: "Version") -> bool:
        assert isinstance(other, Version)

        if self._semver and other._semver:
            return self._semver < other._semver
        else:
            return self._raw < other._raw

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Version)
        # Note: this intentionally compares the raw strings, not the semver objects.
        # e.g. technically "1.0.0" and "001.00.0000" are equivalent semver versions,
        # but we want to treat them as different versions.
        return self._raw == other._raw

    def __str__(self) -> str:
        return self._raw

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

from src.registry_manager.version import Version


def test_version_smaller():
    assert Version("1.0.0") < Version("1.0.1")
    assert Version("1.0.0") < Version("1.1.0")
    assert Version("1.0.0") < Version("2.0.0")
    assert Version("1.0.0-alpha") < Version("1.0.0")
    assert Version("A") < Version("B")


def test_version_equality():
    assert Version("1.0.0") == Version("1.0.0")
    assert not (Version("1.0.0") == Version("2.0.0"))


def test_version_equality_with_non_version():
    """Version.__eq__ must not crash when compared to non-Version objects."""
    # Python evaluates to False (via NotImplemented fallback) for mismatched types
    assert (Version("1.0.0") == None) is False  # noqa: E711
    assert (Version("0.0.0") == None) is False  # noqa: E711
    assert (Version("1.0.0") == 1) is False
    assert (Version("1.0.0") == "1.0.0") is False
    # Comparison must also work in the reverse direction
    assert (None == Version("1.0.0")) is False  # noqa: E711

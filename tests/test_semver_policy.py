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

from pathlib import Path

from src.registry_manager import BazelModuleInfo
from src.registry_manager.main import is_release_semver_acceptable
from src.registry_manager.version import Version

EXAMPLE_MODULE = BazelModuleInfo(
    path=Path("example/path"),
    name="example-module",
    org_and_repo="example_org/example_repo",
    versions=[
        Version("1.5.5"),
        Version("2.0.1-alpha.5"),
    ],
    periodic_pull=True,
    obsolete=False,
)


def verify_new_version(version: str) -> bool:
    return is_release_semver_acceptable(EXAMPLE_MODULE, Version(version))


def test_bumping_patch_version():
    assert verify_new_version("1.5.6-alpha")
    assert verify_new_version("1.5.6")

    assert verify_new_version("2.0.1-beta")
    assert verify_new_version("2.0.1")

    assert verify_new_version("2.0.2-beta")
    assert verify_new_version("2.0.2")


def test_release_of_existing_versions():
    assert not verify_new_version("1.5.5")
    assert not verify_new_version("2.0.1-alpha.5")


def test_backwards_patch():
    assert not verify_new_version("1.5.0")
    assert not verify_new_version("1.5.4")
    assert not verify_new_version("2.0.0")


def test_minor_version_bump():
    assert verify_new_version("1.6.0")
    assert verify_new_version("2.1.0")
    assert verify_new_version("2.42.0")


def test_major_version_bump():
    assert verify_new_version("3.0.0")
    assert verify_new_version("42.0.0")


def test_patch_of_old_release():
    # Even though 1.5.5 exists, a patch to an older minor version is acceptable
    assert verify_new_version("1.4.9")


def test_backwards_patch_suffix():
    # As 2.0.1-alpha.5 exists, a lower prerelease suffix is not acceptable
    assert not verify_new_version("2.0.1-alpha")
    assert not verify_new_version("2.0.1-alpha.4")


def test_forward_patch_suffix():
    # A higher prerelease suffix is acceptable
    assert verify_new_version("2.0.1-alpha.6")
    assert verify_new_version("2.0.1-beta")


def test_prerelease_after_release():
    # A prerelease after the released version is not acceptable
    assert not verify_new_version("1.5.5-alpha")


def test_all_bets_are_off_for_non_semver():
    assert not verify_new_version("foo")

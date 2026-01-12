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

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from src.registry_manager.main import plan_module_updates
from tests.conftest import make_module_info, make_release_info


def test_plan_finds_module_needing_update():
    # Module has version 1.0.0
    module_current_version = "1.0.0"
    module = make_module_info(versions=[module_current_version])

    # New release is version 2.0.0 (higher than current)
    new_release_version = "2.0.0"
    expected_comp_level = 2

    gh = MagicMock()
    gh.get_latest_release.return_value = make_release_info(version=new_release_version)
    # Mock module file content from the release
    gh.try_get_module_file_content.return_value = f'module(version="{new_release_version}", compatibility_level={expected_comp_level})'

    plan = plan_module_updates(Namespace(modules=[]), gh, [module])

    # Should plan update since 2.0.0 > 1.0.0
    assert len(plan) == 1
    assert plan[0].module.name == "score_demo"  # Default name from fixture
    assert str(plan[0].release.version) == new_release_version


def test_plan_skips_uptodate_modules():
    # Module already has the latest version (2.0.0) plus an older one
    latest_version = "2.0.0"
    module = make_module_info(versions=[latest_version, "1.0.0"])

    gh = MagicMock()
    # Latest release is 2.0.0, which module already has
    gh.get_latest_release.return_value = make_release_info(version=latest_version)

    plan = plan_module_updates(Namespace(modules=[]), gh, [module])

    # Should not plan any updates since module is already up-to-date
    assert len(plan) == 0
    # Should not even try to fetch module file content
    gh.try_get_module_file_content.assert_not_called()


def test_plan_handles_missing_module_file():
    # Module needs update (current: 1.0.0, release: 2.0.0)
    module = make_module_info(versions=["1.0.0"])
    new_version = "2.0.0"

    gh = MagicMock()
    gh.get_latest_release.return_value = make_release_info(version=new_version)
    # MODULE.bazel file is missing from the release (returns None)
    gh.try_get_module_file_content.return_value = None

    plan = plan_module_updates(Namespace(modules=[]), gh, [module])

    # Should not plan update if MODULE.bazel file is missing
    assert len(plan) == 0


def _get_warnings(capsys: pytest.CaptureFixture[str]) -> list[str]:
    return [
        line
        for line in capsys.readouterr().out.splitlines()
        if "warning" in line.lower()
    ]


def test_plan_skips_non_semver_release(
    capsys: pytest.CaptureFixture[str],
):
    # Module has version 1.0.0
    module_current_version = "1.0.0"
    module = make_module_info(versions=[module_current_version])

    # New release is version "ABC" (non-semver)
    new_release_version = "ABC"

    gh = MagicMock()
    gh.get_latest_release.return_value = make_release_info(version=new_release_version)
    # MODULE.bazel file is missing from the release (returns None)
    gh.try_get_module_file_content.return_value = None

    plan = plan_module_updates(Namespace(modules=[]), gh, [module])

    # Should plan not update since the release version is non-semver
    assert len(plan) == 0

    # Verify a warning was printed
    warning_messages = _get_warnings(capsys)
    msg = [m for m in warning_messages if new_release_version in m]
    assert len(msg) >= 1
    assert "is not a valid semantic version" in msg[0]

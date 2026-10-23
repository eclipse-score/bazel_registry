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

import json
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

    gh = MagicMock()
    gh.get_latest_release.return_value = make_release_info(version=new_release_version)
    # Mock module file content from the release
    gh.try_get_module_file_content.return_value = (
        f'module(version="{new_release_version}")'
    )

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
        for line in capsys.readouterr().err.splitlines()
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


def test_plan_source_only_migration(tmp_path):
    """
    Verifies that a source-only migration is planned when an existing version
    can be moved from a dynamic archive to a stable release asset.
    """
    # Arrange
    # 1. Create a mock registry structure
    module_path = tmp_path / "modules" / "score_demo"
    version_path = module_path / "1.0.0"
    version_path.mkdir(parents=True)

    # The existing source.json points to a dynamic archive
    source_content = {
        "url": "https://github.com/org/repo/archive/refs/tags/v1.0.0.tar.gz",
        "integrity": "old-integrity-hash",
        "strip_prefix": "repo-1.0.0",
    }
    (version_path / "source.json").write_text(json.dumps(source_content))

    # 2. Create module info pointing to the temp registry
    module = make_module_info(versions=["1.0.0"])
    module.path = module_path

    # 3. Mock GithubWrapper to return a release that HAS a stable asset URL
    gh = MagicMock()
    release_info = make_release_info(version="1.0.0")
    release_info.asset_url = (
        "https://github.com/org/repo/releases/download/v1.0.0/bzlmod-v1.0.0.tar.gz"
    )
    gh.get_latest_release.return_value = release_info

    # Act
    plan = plan_module_updates(Namespace(modules=[]), gh, [module])

    # Assert
    assert len(plan) == 1
    update_task = plan[0]
    assert str(update_task.release.version) == "1.0.0"
    # The key assertion: mod_file is None to signal a source-only migration
    assert update_task.mod_file is None

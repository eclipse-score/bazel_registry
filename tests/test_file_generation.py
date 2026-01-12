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
import os
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from src.registry_manager.bazel_wrapper import ModuleUpdateRunner
from tests.conftest import make_update_info


class TestFileGeneration:
    """Test generating registry files."""

    def test_generates_source_json(
        self,
        basic_registry_setup: Callable[..., None],
    ) -> None:
        basic_registry_setup()
        os.chdir("/")

        # Setup: module score_demo with org/repo, release version 1.0.0
        version = "1.0.0"
        org_repo = "org/repo"
        update_info = make_update_info(version=version)
        # Note: make_update_info defaults to org/repo, but we're being explicit here

        # Mock sha256 calculation to return a test value
        mock_sha256 = "sha256-test"
        runner = ModuleUpdateRunner(update_info)
        with patch(
            "src.registry_manager.bazel_wrapper.sha256_from_url",
            return_value=mock_sha256,
        ):
            runner.generate_files()

        # Verify source.json contains the correct URL and integrity
        source_file = Path("/modules/score_demo/1.0.0/source.json")
        assert source_file.exists()
        source = json.loads(source_file.read_text())
        assert (
            source["url"]
            == f"https://github.com/{org_repo}/archive/refs/tags/v{version}.tar.gz"
        )
        assert source["integrity"] == mock_sha256

    def test_generates_module_file(
        self,
        basic_registry_setup: Callable[..., None],
    ) -> None:
        basic_registry_setup()
        os.chdir("/")

        # When version and comp_level match, no patching is needed
        version = "1.0.0"
        comp_level = 1  # Defaults to first digit of version
        update_info = make_update_info(version=version)

        runner = ModuleUpdateRunner(update_info)
        with patch(
            "src.registry_manager.bazel_wrapper.sha256_from_url",
            return_value="sha256-test",
        ):
            runner.generate_files()

        # Verify MODULE.bazel is created with correct version and compatibility
        module_file = Path("/modules/score_demo/1.0.0/MODULE.bazel")
        assert module_file.exists()
        expected = f'module(version="{version}", compatibility_level={comp_level})'
        assert expected in module_file.read_text()

    @pytest.mark.parametrize(
        "release_version,module_version,module_comp_level,expected_comp_level",
        [
            # Case 1: Release is v2.0.0, but MODULE.bazel says
            # version="1.0.0". Patch needed to change version from
            # 1.0.0 to 2.0.0, and comp_level from 1 to 2
            ("2.0.0", "1.0.0", 1, 2),
            # Case 2: Release is v3.0.0, MODULE.bazel says
            # version="3.0.0" but comp_level=1. Patch needed to
            # change comp_level from 1 to 3 (should match major)
            ("3.0.0", "3.0.0", 1, 3),
            # Case 3: Both mismatches
            ("2.3.4", "1.5.0", 1, 2),
            # Case 4: Release is "ABC", MODULE.bazel says version="1.0.0".
            # Patch needed to change version to "ABC". Compatibility
            # level remains as-is, as it cannot be derived from non-semver.
            ("ABC", "1.0.0", 42, 42),
        ],
    )
    def test_creates_patch_when_mismatch(
        self,
        basic_registry_setup: Callable[..., None],
        release_version: str,
        module_version: str,
        module_comp_level: int,
        expected_comp_level: int,
    ) -> None:
        """Test patches for MODULE.bazel version/comp_level mismatches."""
        basic_registry_setup()
        os.chdir("/")

        # Setup: GitHub release is at release_version, but the
        # MODULE.bazel file in that release declares module_version
        # with module_comp_level
        update_info = make_update_info(
            version=release_version,  # What GitHub says
            module_version=module_version,  # What MODULE.bazel says
            comp_level=module_comp_level,  # What MODULE.bazel has
        )

        runner = ModuleUpdateRunner(update_info)
        with patch(
            "src.registry_manager.bazel_wrapper.sha256_from_url",
            return_value="sha256-test",
        ):
            runner.generate_files()

        # When there's a mismatch, a patch should be created
        patches_dir = Path(f"/modules/score_demo/{release_version}/patches")
        assert patches_dir.exists()

        patch_file = patches_dir / "module_dot_bazel_version.patch"
        assert patch_file.exists()

        # Patch should correct the version and compatibility_level
        patch_content = patch_file.read_text()
        assert f'version="{release_version}"' in patch_content
        assert f"compatibility_level={expected_comp_level}" in patch_content

        # MODULE.bazel file should reflect the patched version/comp_level, not
        # the original ones!
        mod = Path(f"/modules/score_demo/{release_version}/MODULE.bazel").read_text()
        assert release_version in mod
        if module_version != release_version:
            assert module_version not in mod

    def test_no_patch_when_versions_match(
        self,
        basic_registry_setup: Callable[..., None],
    ) -> None:
        basic_registry_setup()
        os.chdir("/")

        # When release version matches MODULE.bazel version and
        # comp_level is correct, no patch should be generated
        version = "1.0.0"
        update_info = make_update_info(
            version=version,
            module_version=version,  # Same as release
            comp_level=1,  # Matches major version
        )

        runner = ModuleUpdateRunner(update_info)
        with patch(
            "src.registry_manager.bazel_wrapper.sha256_from_url",
            return_value="sha256-test",
        ):
            runner.generate_files()

        # Verify no patches section in source.json
        source_path = Path("/modules/score_demo/1.0.0/source.json")
        source = json.loads(source_path.read_text())
        assert "patches" not in source

    def test_appends_version_with_semver_sorting(
        self,
        basic_registry_setup: Callable[..., None],
    ) -> None:
        # Setup: metadata.json has versions 1.0.9 and 1.0.10
        # Note: 1.0.10 > 1.0.9 in semver (not lexical where "10" < "9")
        existing = ["1.0.9", "1.0.10"]
        basic_registry_setup(versions=existing)
        os.chdir("/")

        # Add new version 1.0.11
        new_version = "1.0.11"
        update_info = make_update_info(
            version=new_version,
            existing_versions=existing,
        )

        runner = ModuleUpdateRunner(update_info)
        with patch(
            "src.registry_manager.bazel_wrapper.sha256_from_url",
            return_value="sha256-test",
        ):
            runner.generate_files()

        # Verify versions are sorted descending by semver (newest first)
        metadata_path = Path("/modules/score_demo/metadata.json")
        metadata = json.loads(metadata_path.read_text())
        generated_versions = metadata["versions"]
        expected_versions = ["1.0.11", "1.0.10", "1.0.9"]
        assert generated_versions == expected_versions

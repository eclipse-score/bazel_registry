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
from collections.abc import Callable

import pytest

from src.registry_manager.bazel_wrapper import read_modules


class TestModuleReading:
    """Test reading and filtering modules."""

    def test_read_specific_modules_by_name(
        self, setup_module_metadata: Callable[[dict], None]
    ) -> None:
        module_name = "score_alpha"
        module_repo = "github:org/alpha"
        module_version = "1.0.0"

        setup_module_metadata(
            {
                module_name: {
                    "repository": [module_repo],
                    "versions": [module_version],
                }
            }
        )
        os.chdir("/")

        modules = read_modules([module_name])
        assert len(modules) == 1
        assert modules[0].name == module_name

    def test_filter_out_obsolete_modules(
        self, setup_module_metadata: Callable[[dict], None]
    ) -> None:
        active_module = "score_active"
        obsolete_module = "score_old"

        setup_module_metadata(
            {
                active_module: {
                    "repository": ["github:org/repo"],
                    "obsolete": False,  # Should be included
                },
                obsolete_module: {
                    "repository": ["github:org/repo"],
                    "obsolete": True,  # Should be filtered out
                },
            }
        )
        os.chdir("/")

        modules = read_modules(None)
        names = {m.name for m in modules}
        assert active_module in names
        assert obsolete_module not in names

    def test_filter_out_non_github_modules(
        self, setup_module_metadata: Callable[[dict], None]
    ) -> None:
        github_module = "score_github"
        gitlab_module = "score_gitlab"

        setup_module_metadata(
            {
                github_module: {
                    "repository": ["github:org/repo"],  # Should be included
                },
                gitlab_module: {
                    "repository": ["gitlab:org/repo"],  # Should be filtered out
                },
            }
        )
        os.chdir("/")

        modules = read_modules(None)
        names = {m.name for m in modules}
        assert github_module in names
        assert gitlab_module not in names

    def test_versions_sorted_semver_desc(
        self, setup_module_metadata: Callable[[dict], None]
    ) -> None:
        module_name = "score_semver"
        # Versions in unsorted order
        unsorted_versions = ["1.0.9", "1.0.10", "1.0.2"]
        # Expected: sorted descending by semver (not lexical)
        expected_sorted = ["1.0.10", "1.0.9", "1.0.2"]
        expected_latest = "1.0.10"  # Highest version

        setup_module_metadata(
            {
                module_name: {
                    "repository": ["github:org/repo"],
                    "versions": unsorted_versions,
                }
            }
        )
        os.chdir("/")

        modules = read_modules(None)
        assert modules[0].versions == expected_sorted
        assert modules[0].latest_version == expected_latest

    def test_invalid_versions_raise(
        self, setup_module_metadata: Callable[[dict], None]
    ) -> None:
        # These versions should cause validation to fail
        invalid_versions = ["1.0", "not-a-version"]

        setup_module_metadata(
            {
                "score_bad": {
                    "repository": ["github:org/repo"],
                    "versions": invalid_versions,
                }
            }
        )
        os.chdir("/")

        # Should raise SystemExit due to invalid version format
        with pytest.raises(SystemExit):
            read_modules(None)

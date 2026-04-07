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
from collections.abc import Callable
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest
from src.registry_manager.main import main

from tests.conftest import make_release_info


def test_all_correct(
    build_fake_filesystem: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When all modules have compatibility_level matching major version, all is well."""
    build_fake_filesystem(
        {
            "modules": {
                "score_correct_module": {
                    "metadata.json": json.dumps(
                        {
                            "versions": ["1.0.0", "2.0.0"],
                            "repository": ["github:org/repo"],
                        }
                    ),
                    "1.0.0": {
                        "MODULE.bazel": (
                            "module(name='score_correct_module', "
                            "version='1.0.0', compatibility_level=1)\n"
                        )
                    },
                    "2.0.0": {
                        "MODULE.bazel": (
                            "module(name='score_correct_module', "
                            "version='2.0.0', compatibility_level=2)\n"
                        )
                    },
                }
            }
        }
    )
    with patch("src.registry_manager.main.GithubWrapper") as mock_gh_class:
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        mock_gh.try_get_module_file_content.return_value = None
        with suppress(SystemExit):
            main(["--github-token", "FAKE_TOKEN"])
    captured = capsys.readouterr()
    warning_messages = [
        line for line in captured.err.splitlines() if "warning" in line.lower()
    ]
    if warning_messages:
        print("Full log: ", captured.err)
    assert warning_messages == []
    assert (
        captured.out
        == "NOTICE: src.registry_manager.main All modules are up to date; no updates needed.\n"
    )


def test_stdout_only_contains_final_summary(
    build_fake_filesystem: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_fake_filesystem(
        {
            "modules": {
                "score_demo": {
                    "metadata.json": json.dumps(
                        {
                            "versions": ["1.0.0"],
                            "repository": ["github:org/repo"],
                            "periodic-pull": True,
                        }
                    )
                }
            }
        }
    )

    with (
        patch("src.registry_manager.main.GithubWrapper") as mock_gh_class,
        patch("src.registry_manager.main.ModuleUpdateRunner") as mock_runner_class,
    ):
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        mock_gh.get_latest_release.return_value = make_release_info(version="2.0.0")
        mock_gh.try_get_module_file_content.return_value = (
            'module(version="2.0.0", compatibility_level=2)'
        )

        main(["--github-token", "FAKE_TOKEN"])

    captured = capsys.readouterr()
    assert (
        captured.out
        == "NOTICE: src.registry_manager.main Updating score_demo from 1.0.0 to 2.0.0\n"
    )
    assert (
        "NOTICE: src.registry_manager.main Updating score_demo from 1.0.0 to 2.0.0"
        not in captured.err
    )
    assert "Checking module score_demo..." in captured.err
    mock_runner_class.return_value.generate_files.assert_called_once()

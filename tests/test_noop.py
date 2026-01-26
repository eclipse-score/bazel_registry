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
    captured: str = capsys.readouterr().out
    warning_messages = [
        line for line in captured.splitlines() if "warning" in line.lower()
    ]
    assert len(warning_messages) == 0

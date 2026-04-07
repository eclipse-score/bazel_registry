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
from unittest.mock import MagicMock, patch

import pytest
from src.registry_manager.main import main

from tests.conftest import make_release_info


def test_cli_reports_no_updates_in_text_mode(
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
                        }
                    ),
                }
            }
        }
    )

    with patch("src.registry_manager.main.GithubWrapper") as mock_gh_class:
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        main(["--github-token", "FAKE_TOKEN"])

    captured = capsys.readouterr()
    assert captured.out == "All modules are up to date; no updates needed.\n"
    assert "warning" not in captured.err.lower()
    mock_gh.get_latest_release.assert_not_called()


def test_cli_applies_updates_and_prints_text_report(
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
    assert captured.out == "Updated 1 module(s):\n- score_demo: 1.0.0 -> 2.0.0\n"
    assert "Checking module score_demo..." in captured.err
    mock_runner_class.return_value.generate_files.assert_called_once()


def test_cli_json_mode_includes_warnings_and_exits_nonzero(
    build_fake_filesystem: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_fake_filesystem(
        {
            "modules": {
                "score_bad": {
                    "metadata.json": json.dumps(
                        {
                            "versions": ["1.0.0"],
                        }
                    )
                }
            }
        }
    )

    with pytest.raises(SystemExit, match="1"):
        main(["--github-token", "FAKE_TOKEN", "--format", "json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["has_updates"] is False
    assert "commit_msg" not in output
    assert "WARNING: src.registry_manager.bazel_wrapper" in captured.err
    assert "ERROR: src.registry_manager.main Completed with 1 warnings." in captured.err

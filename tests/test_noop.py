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
    assert captured.out == "All modules are up to date; no updates needed.\n"


def test_text_mode_prints_human_summary_to_stdout(
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


def test_format_json_no_updates(
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
                    )
                }
            }
        }
    )
    with patch("src.registry_manager.main.GithubWrapper") as mock_gh_class:
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        mock_gh.get_latest_release.return_value = make_release_info(version="1.0.0")
        main(["--github-token", "FAKE_TOKEN", "--format", "json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["has_updates"] is False
    assert output["commit_msg"] is None
    assert output["pr_title"] == "Update modules"
    assert output["pr_commit_msg"] == "Update modules"
    assert (
        output["pr_body"] == "This PR updates the modules to their latest versions.\n"
        "Please review and merge if everything looks good.\n\n"
        "No module updates were needed."
    )
    assert output["updated_modules"] == []
    assert output["warnings"] == []


def test_format_json_single_update(
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
        patch("src.registry_manager.main.ModuleUpdateRunner"),
    ):
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        mock_gh.get_latest_release.return_value = make_release_info(version="2.0.0")
        mock_gh.try_get_module_file_content.return_value = (
            'module(version="2.0.0", compatibility_level=2)'
        )
        main(["--github-token", "FAKE_TOKEN", "--format", "json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["has_updates"] is True
    assert output["commit_msg"] == "chore: update score_demo to 2.0.0"
    assert output["pr_title"] == "chore: update score_demo to 2.0.0"
    assert output["pr_commit_msg"] == "chore: update score_demo to 2.0.0"
    assert (
        output["pr_body"] == "This PR updates the modules to their latest versions.\n"
        "Please review and merge if everything looks good.\n\n"
        "- score_demo: 1.0.0 -> 2.0.0"
    )
    assert output["updated_modules"] == [
        {
            "name": "score_demo",
            "from_version": "1.0.0",
            "to_version": "2.0.0",
        }
    ]
    assert output["warnings"] == []


def test_format_json_multiple_updates(
    build_fake_filesystem: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_fake_filesystem(
        {
            "modules": {
                "score_alpha": {
                    "metadata.json": json.dumps(
                        {
                            "versions": ["1.0.0"],
                            "repository": ["github:org/alpha"],
                            "periodic-pull": True,
                        }
                    )
                },
                "score_beta": {
                    "metadata.json": json.dumps(
                        {
                            "versions": ["1.0.0"],
                            "repository": ["github:org/beta"],
                            "periodic-pull": True,
                        }
                    )
                },
            }
        }
    )
    with (
        patch("src.registry_manager.main.GithubWrapper") as mock_gh_class,
        patch("src.registry_manager.main.ModuleUpdateRunner"),
    ):
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        mock_gh.get_latest_release.return_value = make_release_info(version="2.0.0")
        mock_gh.try_get_module_file_content.return_value = (
            'module(version="2.0.0", compatibility_level=2)'
        )
        main(["--github-token", "FAKE_TOKEN", "--format", "json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["has_updates"] is True
    commit_msg = output["commit_msg"]
    assert commit_msg.startswith("chore: update multiple modules")
    assert output["pr_title"] == "chore: update multiple modules"
    assert output["pr_commit_msg"] == commit_msg
    assert "score_alpha -> 2.0.0" in commit_msg
    assert "score_beta -> 2.0.0" in commit_msg
    assert "Please review and merge if everything looks good." in output["pr_body"]
    assert "- score_alpha: 1.0.0 -> 2.0.0" in output["pr_body"]
    assert "- score_beta: 1.0.0 -> 2.0.0" in output["pr_body"]
    assert {item["name"] for item in output["updated_modules"]} == {
        "score_alpha",
        "score_beta",
    }
    assert all(item["from_version"] == "1.0.0" for item in output["updated_modules"])
    assert all(item["to_version"] == "2.0.0" for item in output["updated_modules"])
    assert output["warnings"] == []


def test_format_json_includes_warnings_and_exits_nonzero(
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
    assert output["commit_msg"] is None
    assert output["pr_title"] == "Update modules"
    assert output["pr_commit_msg"] == "Update modules"
    assert "No module updates were needed." in output["pr_body"]
    assert output["updated_modules"] == []
    assert any("invalid repository field" in warning for warning in output["warnings"])
    assert "WARNING: src.registry_manager.bazel_wrapper" in captured.err
    assert "ERROR: src.registry_manager.main Completed with 1 warnings." in captured.err

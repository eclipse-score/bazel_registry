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

from src.registry_manager import ModuleUpdateInfo
from src.registry_manager.main import RegistryRunResult, _format_github_output

from tests.conftest import make_update_info


def make_run_result(
    updated_modules: list[ModuleUpdateInfo] | None = None,
    warnings: list[str] | None = None,
) -> RegistryRunResult:
    return RegistryRunResult(
        updated_modules=updated_modules or [],
        warnings=warnings or [],
    )


def test_render_text_without_updates() -> None:
    result = make_run_result()

    assert result.render(None) == "All modules are up to date; no updates needed."


def test_render_text_with_updates_and_warnings() -> None:
    result = make_run_result(
        updated_modules=[
            make_update_info(
                version="2.0.0",
                existing_versions=["1.0.0"],
            )
        ],
        warnings=["Could not retrieve metadata for score_other."],
    )

    assert (
        result.render(None)
        == """Updated 1 module(s):
- score_demo: 1.0.0 -> 2.0.0

1 warning(s):
- Could not retrieve metadata for score_other."""
    )


def test_render_json_without_updates_omits_pr_fields() -> None:
    result = make_run_result()

    assert json.loads(result.render("json")) == {"has_updates": False}


def test_render_json_with_single_update() -> None:
    result = make_run_result(
        updated_modules=[
            make_update_info(
                version="2.0.0",
                existing_versions=["1.0.0"],
            )
        ]
    )

    assert json.loads(result.render("json")) == {
        "has_updates": True,
        "commit_msg": "feat: update score_demo to 2.0.0",
        "pr_title": "feat: update score_demo to 2.0.0",
        "pr_body": (
            "This PR updates the modules to their latest versions.\n"
            "Please review and merge if everything looks good.\n\n"
            "Updated 1 module(s):\n"
            "- score_demo: 1.0.0 -> 2.0.0"
        ),
    }


def test_render_json_with_multiple_updates() -> None:
    result = make_run_result(
        updated_modules=[
            make_update_info(
                module_name="score_alpha",
                version="2.0.0",
                existing_versions=["1.0.0"],
            ),
            make_update_info(
                module_name="score_beta",
                version="3.0.0",
                existing_versions=["2.0.0"],
            ),
        ]
    )

    assert json.loads(result.render("json")) == {
        "has_updates": True,
        "commit_msg": (
            "feat: update multiple modules\n\n"
            "- score_alpha -> 2.0.0\n"
            "- score_beta -> 3.0.0"
        ),
        "pr_title": "feat: update multiple modules",
        "pr_body": (
            "This PR updates the modules to their latest versions.\n"
            "Please review and merge if everything looks good.\n\n"
            "Updated 2 module(s):\n"
            "- score_alpha: 1.0.0 -> 2.0.0\n"
            "- score_beta: 2.0.0 -> 3.0.0"
        ),
    }


def test_render_github_output_without_updates() -> None:
    result = make_run_result()

    assert result.render("github_output") == "has_updates=false\n"


def test_render_github_output_with_single_update() -> None:
    result = make_run_result(
        updated_modules=[
            make_update_info(
                version="2.0.0",
                existing_versions=["1.0.0"],
            )
        ]
    )

    assert (
        result.render("github_output")
        == """has_updates=true
commit_msg=feat: update score_demo to 2.0.0
pr_title=feat: update score_demo to 2.0.0
pr_body<<EOF
This PR updates the modules to their latest versions.
Please review and merge if everything looks good.

Updated 1 module(s):
- score_demo: 1.0.0 -> 2.0.0
EOF
"""
    )


def test_format_github_output_uses_unique_delimiter_for_multiline_values() -> None:
    assert (
        _format_github_output("pr_body", "First line\nEOF\nLast line")
        == """pr_body<<EOF_X
First line
EOF
Last line
EOF_X
"""
    )

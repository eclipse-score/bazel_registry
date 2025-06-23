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

"""
Purpose:
    This registry uses semantic versioning (semver), but Bazel itself does not
    interpret version numbers as semver. Instead, Bazel relies on the
    `compatibility_level` field to determine breaking changes and module
    compatibility. This script ensures that every module version in the registry
    has a `compatibility_level` in its `MODULE.bazel` file matching the major
    version of the module. This alignment enforces semver expectations for users
    and Bazel tooling, helping maintainers and users avoid surprises and enforce
    good versioning practices.
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

GIT_ROOT = Path(__file__).parent.parent
MODULES_DIR = GIT_ROOT / "modules"


def extract_major_version(version: str):
    """
    Extract the major version number from a version string (e.g., '2.1.0' -> 2).
    """
    return int(version.split(".")[0])


def parse_compatibility_level(module_bazel_path: Path):
    """
    Parse the compatibility_level integer from a MODULE.bazel file.
    Returns None if not found.
    """
    content = module_bazel_path.read_text()
    m = re.search(r"compatibility_level\s*=\s*(\d+)", content)
    if m:
        return int(m.group(1))
    return None


def is_running_in_github_actions():
    return "GITHUB_ACTIONS" in os.environ


@dataclass
class CheckResult:
    type: str  # 'ok', 'warning', 'error'
    file: Path
    msg: str
    line: int = 1


def analyze(modules_dir: Path) -> list[CheckResult]:
    """
    For each module and each version listed in its metadata.json, check that
    the MODULE.bazel file contains a compatibility_level matching the major
    version. Returns a list of CheckResult objects for reporting.
    """
    results: list[CheckResult] = []
    for module in modules_dir.iterdir():
        meta_path = module / "metadata.json"
        with meta_path.open() as f:
            meta: dict[str, object] = json.load(f)
        versions = meta.get("versions", [])
        assert isinstance(versions, list), "Versions should be a list"
        for version in versions:
            assert isinstance(version, str), "Version should be a string"
            mod_bazel = module / version / "MODULE.bazel"
            major = extract_major_version(version)
            compatibility_level = parse_compatibility_level(mod_bazel)
            if compatibility_level is None:
                results.append(
                    CheckResult(
                        type="warning",
                        file=mod_bazel,
                        msg="missing compatibility_level",
                    )
                )
            elif compatibility_level != major:
                results.append(
                    CheckResult(
                        type="error",
                        file=mod_bazel,
                        msg=f"compatibility_level {compatibility_level} does not match "
                        + f"major version {major} (from version {version})",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        type="ok",
                        file=mod_bazel,
                        msg=f"compatibility_level {compatibility_level} matches "
                        + f"major version {major}",
                    )
                )
    return results


def print_results(results: list[CheckResult], gha: bool):
    """
    Print the results of the compatibility check. Formats output for local
    runs or GitHub Actions as appropriate.
    """
    for r in results:
        file = r.file.relative_to(GIT_ROOT)
        if r.type == "ok":
            if not gha:
                print(f"✅ OK: {file} {r.msg}")
        elif r.type == "warning":
            if gha:
                print(f"::error file={file},line={r.line}::{r.msg}")
            else:
                print(f"⚠️ WARNING: {file} {r.msg}")
        elif r.type == "error":
            if gha:
                print(f"::error file={file},line={r.line}::{r.msg}")
            else:
                print(f"❌ ERROR: {file} {r.msg}")


if __name__ == "__main__":
    results = analyze(MODULES_DIR)
    gha = is_running_in_github_actions()

    print_results(results, gha)

    any_error = any(r.type == "error" for r in results)
    if any_error:
        if not gha:
            print("\n❌ Some modules have incorrect compatibility_level.")
        sys.exit(1)
    else:
        if not gha:
            print("\n✅ All modules have correct compatibility_level.")
        sys.exit(0)

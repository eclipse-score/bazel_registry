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
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from src.registry_manager import BazelModuleInfo, ModuleUpdateInfo, Version
from src.registry_manager.bazel_wrapper import ModuleFileContent, ModuleUpdateRunner
from src.registry_manager.gh_logging import Logger
from src.registry_manager.github_wrapper import GitHubReleaseInfo


class MockLogger(Logger):
    """Logger that captures messages for testing."""

    def __init__(self):
        super().__init__("test")
        self.debug_messages: list[str] = []
        self.info_messages: list[str] = []
        self.warning_messages: list[str] = []
        self.error_messages: list[str] = []

    def _print(
        self, prefix: str, msg: str, file: Path | None = None, line: int | None = None
    ) -> None:
        if prefix == "debug":
            self.debug_messages.append(msg)
        elif prefix == "info":
            self.info_messages.append(msg)
        elif prefix == "warning":
            self.warning_messages.append(msg)
        elif prefix == "error":
            self.error_messages.append(msg)


@pytest.fixture
def mock_logger() -> MockLogger:
    """Create a mock logger for testing."""
    return MockLogger()


@pytest.fixture
def build_fake_filesystem(fs: Any):
    """Convenience helper to build a fake filesystem from a nested dict."""

    def _build(structure: dict[str, object], base_path: str = "") -> None:
        base = base_path or "/"
        for name, value in structure.items():
            path = f"{base.rstrip('/')}/{name}"
            if isinstance(value, dict):
                fs.makedirs(path, exist_ok=True)
                _build(value, path)
            else:
                fs.create_file(path, contents=value)

    return _build


@pytest.fixture
def basic_registry_setup(build_fake_filesystem):
    """Setup a basic registry with score_demo module."""

    def _setup(versions: list[str] | None = None) -> None:
        build_fake_filesystem(
            {
                "modules": {
                    "score_demo": {
                        "metadata.json": json.dumps(
                            {
                                "versions": versions or [],
                                "repository": ["github:org/repo"],
                            }
                        )
                    }
                }
            }
        )

    return _setup


def make_module_info(
    name: str = "score_demo",
    org_and_repo: str = "org/repo",
    versions: list[str] | None = None,
    periodic_pull: bool = True,
    obsolete: bool = False,
) -> BazelModuleInfo:
    return BazelModuleInfo(
        path=Path(f"/modules/{name}"),
        name=name,
        org_and_repo=org_and_repo,
        versions=[Version(v) for v in (versions or [])],
        periodic_pull=periodic_pull,
        obsolete=obsolete,
    )


def make_release_info(
    version: str = "1.0.0",
    tag_name: str | None = None,
    prerelease: bool = False,
    org_and_repo: str = "org/repo",
) -> GitHubReleaseInfo:
    if tag_name is None:
        tag_name = f"v{version}"

    return GitHubReleaseInfo(
        org_and_repo=org_and_repo,
        version=Version(version),
        tag_name=tag_name,
        published_at=datetime(2024, 1, 1),
        prerelease=prerelease,
    )


def make_module_content(
    version: str = "1.0.0",
    comp_level: int | None = None,
) -> ModuleFileContent:
    """Factory for creating ModuleFileContent objects."""

    if comp_level is None:
        comp_level = int(version.split(".")[0])

    return ModuleFileContent(
        content=f'module(version="{version}", compatibility_level={comp_level})',
        comp_level=comp_level,
        version=Version(version),
    )


def make_update_info(
    version: str = "1.0.0",
    module_version: str | None = None,
    comp_level: int | None = None,
    module_name: str = "score_demo",
    existing_versions: list[str] | None = None,
) -> ModuleUpdateInfo:
    if module_version is None:
        module_version = version

    return ModuleUpdateInfo(
        module=make_module_info(name=module_name, versions=existing_versions or []),
        release=make_release_info(version=version),
        mod_file=make_module_content(version=module_version, comp_level=comp_level),
    )


def run_file_generation(
    update_info: ModuleUpdateInfo,
) -> ModuleUpdateRunner:
    runner = ModuleUpdateRunner(update_info)
    with patch(
        "src.registry_manager.bazel_wrapper.sha256_from_url",
        return_value="sha256-test",
    ):
        runner.generate_files()
    return runner


@pytest.fixture
def setup_module_metadata(build_fake_filesystem):
    """Setup module metadata files for testing module reading."""

    def _setup(modules_config: dict[str, dict]) -> None:
        """
        Args:
            modules_config: Dict mapping module names to their metadata config.
                          e.g., {"score_demo": {"repository": ["github:org/repo"]}}
        """
        modules_structure = {}
        for module_name, config in modules_config.items():
            modules_structure[module_name] = {"metadata.json": json.dumps(config)}

        build_fake_filesystem({"modules": modules_structure})

    return _setup

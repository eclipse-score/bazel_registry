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

from dataclasses import dataclass
from pathlib import Path

from .github_wrapper import GitHubReleaseInfo
from .version import Version


@dataclass
class BazelModuleInfo:
    path: Path
    name: str
    org_and_repo: str
    # Sorted list of versions, highest (latest) first
    versions: list[Version]
    periodic_pull: bool
    obsolete: bool

    @property
    def latest_version(self) -> Version:
        # A module must always have at least one version,
        # otherwise it simply does not make sense.
        if not self.versions:
            raise ValueError("No versions available")
        return self.versions[0]


@dataclass
class ModuleFileContent:
    content: str
    comp_level: int | None = None
    version: Version | None = None

    @property
    def major_version(self) -> int | None:
        """Returns None if the version is empty or not a valid semantic version."""
        if self.version and self.version.semver:
            return self.version.semver.major
        else:
            return None


@dataclass
class ModuleUpdateInfo:
    module: BazelModuleInfo
    release: GitHubReleaseInfo

    # Original module file content
    mod_file: ModuleFileContent

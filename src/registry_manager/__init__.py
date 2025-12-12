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


@dataclass
class BazelModuleInfo:
    path: Path
    name: str
    org_and_repo: str
    versions: list[str]
    periodic_pull: bool
    obsolete: bool

    @property
    def latest_version(self) -> str | None:
        """Return the latest semantic version, or None if no versions exist."""
        return self.versions[0] if self.versions else None


@dataclass
class ModuleFileContent:
    content: str
    comp_level: int | None = None
    version: str | None = None

    @property
    def major_version(self) -> int | None:
        return int(self.version.split(".")[0]) if self.version else None


@dataclass
class ModuleUpdateInfo:
    module: BazelModuleInfo
    release: GitHubReleaseInfo
    mod_file: ModuleFileContent

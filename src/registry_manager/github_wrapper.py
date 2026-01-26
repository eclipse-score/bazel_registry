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
from datetime import datetime

import github

from .gh_logging import Logger
from .version import Version

log = Logger(__name__)


@dataclass
class GitHubReleaseInfo:
    org_and_repo: str
    version: Version
    tag_name: str
    published_at: datetime
    prerelease: bool

    @property
    def tarball(self):
        return f"https://github.com/{self.org_and_repo}/archive/refs/tags/{self.tag_name}.tar.gz"


class GithubWrapper:
    """Wrapper around GitHub API for fetching release information and module files."""

    def __init__(self, github_token: str | None):
        self.gh = github.Github(github_token)
        self._release_cache: dict[str, GitHubReleaseInfo | None] = {}
        self._module_file_cache: dict[tuple[str, str], str | None] = {}

    def get_latest_release(self, org_and_repo: str) -> GitHubReleaseInfo | None:
        """Fetch the latest release for a GitHub repository.

        Note: that this is not the one with highest SemVer number,
        it's just the last one that was published.

        Caches results to avoid redundant API calls.
        Returns None if no releases exist or on error.
        """
        if org_and_repo in self._release_cache:
            return self._release_cache[org_and_repo]

        try:
            repo = self.gh.get_repo(org_and_repo)
            all_releases: list[GitHubReleaseInfo] = []
            for release in repo.get_releases():  # type: ignore
                all_releases.append(
                    GitHubReleaseInfo(
                        org_and_repo=org_and_repo,
                        version=Version(release.tag_name.lstrip("v")),
                        tag_name=release.tag_name,
                        published_at=release.published_at,
                        prerelease=release.prerelease,
                    )
                )

            sorted_releases = sorted(
                all_releases, key=lambda r: r.published_at, reverse=True
            )
            result = sorted_releases[0] if sorted_releases else None
            self._release_cache[org_and_repo] = result
            return result

        except github.GithubException as e:
            log.warning(f"Error fetching releases for {org_and_repo}: {e}")
            self._release_cache[org_and_repo] = None
            return None

    def try_get_module_file_content(
        self, org_and_repo: str, git_tag: str
    ) -> str | None:
        """Fetch MODULE.bazel file content from a specific release.

        Caches results to avoid redundant API calls.
        Returns None if the file doesn't exist (404) or on error.
        """
        cache_key = (org_and_repo, git_tag)
        if cache_key in self._module_file_cache:
            return self._module_file_cache[cache_key]

        try:
            repo = self.gh.get_repo(org_and_repo)
            content = repo.get_contents("MODULE.bazel", ref=git_tag)
        except github.GithubException as e:
            if e.status == 404:
                self._module_file_cache[cache_key] = None
                return None
            raise
        except Exception as e:
            log.warning(
                f"Error fetching MODULE.bazel for {org_and_repo}@{git_tag}: {e}"
            )
            self._module_file_cache[cache_key] = None
            return None

        if isinstance(content, list):
            log.warning(f"Unexpected: MODULE.bazel in {org_and_repo} is a directory")
            self._module_file_cache[cache_key] = None
            return None

        try:
            result = content.decoded_content.decode("utf-8")
            self._module_file_cache[cache_key] = result
            return result
        except Exception as e:
            log.warning(
                f"Error decoding MODULE.bazel for {org_and_repo}@{git_tag}: {e}"
            )
            self._module_file_cache[cache_key] = None
            return None

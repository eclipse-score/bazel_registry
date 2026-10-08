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
    private: bool = False
    asset_url: str | None = None

    @property
    def tarball(self) -> str:
        """Archive URL for this release.

        Public repositories prefer explicit release assets (e.g. bzlmod-<tag>.tar.gz)
        attached to the release to guarantee checksum stability. If no explicit asset
        exists, it falls back to the browser-oriented ``codeload`` archive URL.
        Private repositories use the REST API tarball endpoint, which is the only
        authentication.
        """
        if self.private:
            return f"https://api.github.com/repos/{self.org_and_repo}/tarball/{self.tag_name}"
        if self.asset_url:
            return self.asset_url
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
            published_releases = []
            for release in repo.get_releases():  # type: ignore
                # Only published releases count
                if release.published_at:
                    published_releases.append(release)
                else:
                    log.debug(
                        f"Skipping release {release.tag_name} in {org_and_repo} "
                        f"because it is not published yet."
                    )

            if not published_releases:
                self._release_cache[org_and_repo] = None
                return None

            sorted_releases = sorted(
                published_releases, key=lambda r: r.published_at, reverse=True
            )
            latest = sorted_releases[0]

            asset_url = None
            tag_clean = latest.tag_name.lstrip("v")
            candidate_names = {
                f"bzlmod-{latest.tag_name}.tar.gz",
                f"bzlmod-v{tag_clean}.tar.gz",
                f"bzlmod-{tag_clean}.tar.gz",
            }
            assets = list(latest.get_assets())
            for asset in assets:
                if asset.name in candidate_names:
                    asset_url = asset.browser_download_url
                    break
            if not asset_url:
                for asset in assets:
                    if asset.name.startswith("bzlmod-") and asset.name.endswith(
                        ".tar.gz"
                    ):
                        asset_url = asset.browser_download_url
                        break

            if asset_url:
                log.debug(
                    f"Found explicit release asset for {org_and_repo}@{latest.tag_name}: {asset_url}"
                )
            else:
                log.debug(
                    f"No explicit release asset found for {org_and_repo}@{latest.tag_name}; "
                    "falling back to archive link."
                )

            result = GitHubReleaseInfo(
                org_and_repo=org_and_repo,
                version=Version(latest.tag_name.lstrip("v")),
                tag_name=latest.tag_name,
                published_at=latest.published_at,
                prerelease=latest.prerelease,
                private=repo.private,
                asset_url=asset_url,
            )
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

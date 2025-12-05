import logging
import os
from dataclasses import dataclass
from datetime import datetime
from functools import cache

import github

from registry_manager import gh_logging

log = gh_logging.MyLog()

logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))


@dataclass
class ReleaseInfo:
    version: str
    tag_name: str
    tarball: str
    published_at: datetime
    prerelease: bool


class GithubWrapper:
    def __init__(self, github_token: str | None):
        self.gh = github.Github(github_token)

    @cache  # noqa: B019
    def get_latest_release(self, org_and_repo: str) -> ReleaseInfo | None:
        # TODO: this iterates over ALL releases; we typically only need the latest few.
        # Was this because of some strange return ordering from GitHub?
        try:
            repo = self.gh.get_repo(org_and_repo)
            all_releases: list[ReleaseInfo] = []
            for release in repo.get_releases():  # type: ignore
                all_releases.append(
                    ReleaseInfo(
                        version=release.tag_name.lstrip("v"),
                        tag_name=release.tag_name,
                        tarball=f"https://github.com/{org_and_repo}/archive/refs/tags/{release.tag_name}.tar.gz",
                        published_at=release.published_at,
                        prerelease=release.prerelease,
                    )
                )

            all = sorted(all_releases, key=lambda r: r.published_at, reverse=True)
            return all[0] if all else None

        except Exception as e:
            print(f"Error fetching releases for {org_and_repo}: {e}")
            return None

    @cache  # noqa: B019
    def try_get_module_file_content(
        self, org_and_repo: str, version: str
    ) -> str | None:
        repo = self.gh.get_repo(org_and_repo)
        try:
            content = repo.get_contents("MODULE.bazel", ref=f"v{version}")
        except github.GithubException as e:
            if e.status == 404:
                return None
            else:
                raise
        assert not isinstance(content, list)
        return content.decoded_content.decode("utf-8")

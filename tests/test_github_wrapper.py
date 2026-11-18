# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from src.registry_manager.github_wrapper import GitHubReleaseInfo, GithubWrapper
from src.registry_manager.version import Version


class TestGitHubReleaseInfo:
    """Test GitHubReleaseInfo class."""

    def test_tarball_url_uses_codeload_for_public_repo(self) -> None:
        """Public repos use the cache-friendly codeload archive URL."""
        release_info = GitHubReleaseInfo(
            org_and_repo="org/repo",
            version=Version("1.2.3"),
            tag_name="v1.2.3",
            published_at=datetime(2024, 1, 1),
            prerelease=False,
            private=False,
        )

        assert (
            release_info.tarball
            == "https://github.com/org/repo/archive/refs/tags/v1.2.3.tar.gz"
        )

    def test_tarball_url_uses_asset_url_for_public_repo_when_present(self) -> None:
        """Public repos prefer explicit asset URL when available."""
        release_info = GitHubReleaseInfo(
            org_and_repo="org/repo",
            version=Version("1.2.3"),
            tag_name="v1.2.3",
            published_at=datetime(2024, 1, 1),
            prerelease=False,
            private=False,
            asset_url="https://github.com/org/repo/releases/download/v1.2.3/bzlmod-v1.2.3.tar.gz",
        )

        assert release_info.tarball == (
            "https://github.com/org/repo/releases/download/v1.2.3/bzlmod-v1.2.3.tar.gz"
        )

    def test_tarball_url_uses_api_for_private_repo(self) -> None:
        """Private repos use the REST API tarball endpoint (authenticatable)."""
        release_info = GitHubReleaseInfo(
            org_and_repo="org/repo",
            version=Version("1.2.3"),
            tag_name="v1.2.3",
            published_at=datetime(2024, 1, 1),
            prerelease=False,
            private=True,
        )

        assert (
            release_info.tarball
            == "https://api.github.com/repos/org/repo/tarball/v1.2.3"
        )

    def test_tarball_url_uses_api_for_private_repo_even_if_asset_url_set(self) -> None:
        """Private repos always use the REST API tarball endpoint."""
        release_info = GitHubReleaseInfo(
            org_and_repo="org/repo",
            version=Version("1.2.3"),
            tag_name="v1.2.3",
            published_at=datetime(2024, 1, 1),
            prerelease=False,
            private=True,
            asset_url="https://github.com/org/repo/releases/download/v1.2.3/bzlmod-v1.2.3.tar.gz",
        )

        assert (
            release_info.tarball
            == "https://api.github.com/repos/org/repo/tarball/v1.2.3"
        )


class TestGithubWrapper:
    """Test GithubWrapper class."""

    def test_get_latest_release_returns_single_release(self) -> None:
        """Test that get_latest_release returns the single published release."""
        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.target_commitish = "main"
        mock_release.published_at = datetime(2024, 1, 1)
        mock_release.prerelease = False

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [mock_release]
        mock_repo.private = False  # public repo

        with patch.object(GithubWrapper, "__init__", lambda x, y: None):
            wrapper = GithubWrapper(None)
            wrapper.gh = MagicMock()  # type: ignore[attr-defined]
            wrapper.gh.get_repo.return_value = mock_repo  # type: ignore[union-attr]
            wrapper._release_cache = {}  # type: ignore[attr-defined]
            wrapper._module_file_cache = {}  # type: ignore[attr-defined]

            result = wrapper.get_latest_release("eclipse-score/devcontainer")  # type: ignore[attr-defined]

            assert result is not None
            assert result.tag_name == "v1.0.0"
            assert str(result.version) == "1.0.0"
            assert result.tarball == (
                "https://github.com/eclipse-score/devcontainer/archive/refs/tags/v1.0.0.tar.gz"
            )

    def test_get_latest_release_multiple_releases_picks_latest_by_date(self) -> None:
        """Test that get_latest_release picks the most recently published release."""
        # Create mock releases (older first)
        older_release = MagicMock()
        older_release.tag_name = "v1.0.0"
        older_release.target_commitish = "main"
        older_release.published_at = datetime(2024, 1, 1)
        older_release.prerelease = False

        newer_release = MagicMock()
        newer_release.tag_name = "v2.0.0"
        newer_release.target_commitish = "main"
        newer_release.published_at = datetime(2024, 12, 31)
        newer_release.prerelease = False

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [older_release, newer_release]
        mock_repo.private = False  # public repo

        with patch.object(GithubWrapper, "__init__", lambda x, y: None):
            wrapper = GithubWrapper(None)
            wrapper.gh = MagicMock()  # type: ignore[attr-defined]
            wrapper.gh.get_repo.return_value = mock_repo  # type: ignore[union-attr]
            wrapper._release_cache = {}  # type: ignore[attr-defined]
            wrapper._module_file_cache = {}  # type: ignore[attr-defined]

            result = wrapper.get_latest_release("org/repo")  # type: ignore[attr-defined]

            # Should return the newer release
            assert result is not None
            assert result.tag_name == "v2.0.0"

    @pytest.mark.parametrize(
        "asset_name",
        [
            "bzlmod-v1.0.0.tar.gz",
            "bzlmod-1.0.0.tar.gz",
        ],
    )
    def test_get_latest_release_matches_candidate_assets(self, asset_name: str) -> None:
        """Test that get_latest_release selects explicit assets matching naming conventions."""
        mock_asset = MagicMock()
        mock_asset.name = asset_name
        mock_asset.browser_download_url = (
            f"https://github.com/org/repo/releases/download/v1.0.0/{asset_name}"
        )

        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.target_commitish = "main"
        mock_release.published_at = datetime(2024, 1, 1)
        mock_release.prerelease = False
        mock_release.get_assets.return_value = [mock_asset]

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [mock_release]
        mock_repo.private = False

        with patch.object(GithubWrapper, "__init__", lambda x, y: None):
            wrapper = GithubWrapper(None)
            wrapper.gh = MagicMock()  # type: ignore[attr-defined]
            wrapper.gh.get_repo.return_value = mock_repo  # type: ignore[union-attr]
            wrapper._release_cache = {}  # type: ignore[attr-defined]
            wrapper._module_file_cache = {}  # type: ignore[attr-defined]

            result = wrapper.get_latest_release("org/repo")  # type: ignore[attr-defined]

            assert result is not None
            assert result.tarball == mock_asset.browser_download_url

    def test_get_latest_release_skips_asset_discovery_for_private_repo(self) -> None:
        """Test that private repos do not query or use release assets."""
        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.target_commitish = "main"
        mock_release.published_at = datetime(2024, 1, 1)
        mock_release.prerelease = False

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [mock_release]
        mock_repo.private = True

        with patch.object(GithubWrapper, "__init__", lambda x, y: None):
            wrapper = GithubWrapper(None)
            wrapper.gh = MagicMock()  # type: ignore[attr-defined]
            wrapper.gh.get_repo.return_value = mock_repo  # type: ignore[union-attr]
            wrapper._release_cache = {}  # type: ignore[attr-defined]
            wrapper._module_file_cache = {}  # type: ignore[attr-defined]

            result = wrapper.get_latest_release("org/repo")  # type: ignore[attr-defined]

            assert result is not None
            assert (
                result.tarball == "https://api.github.com/repos/org/repo/tarball/v1.0.0"
            )
            mock_release.get_assets.assert_not_called()

    def test_get_latest_release_falls_back_when_no_matching_asset(self) -> None:
        """Test that get_latest_release falls back to archive link when no matching asset exists."""
        non_matching_asset = MagicMock()
        non_matching_asset.name = "source-code.tar.gz"
        non_matching_asset.browser_download_url = (
            "https://github.com/org/repo/releases/download/v1.0.0/source-code.tar.gz"
        )

        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.target_commitish = "main"
        mock_release.published_at = datetime(2024, 1, 1)
        mock_release.prerelease = False
        mock_release.get_assets.return_value = [non_matching_asset]

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [mock_release]
        mock_repo.private = False

        with patch.object(GithubWrapper, "__init__", lambda x, y: None):
            wrapper = GithubWrapper(None)
            wrapper.gh = MagicMock()  # type: ignore[attr-defined]
            wrapper.gh.get_repo.return_value = mock_repo  # type: ignore[union-attr]
            wrapper._release_cache = {}  # type: ignore[attr-defined]
            wrapper._module_file_cache = {}  # type: ignore[attr-defined]

            result = wrapper.get_latest_release("org/repo")  # type: ignore[attr-defined]

            assert result is not None
            assert (
                result.tarball
                == "https://github.com/org/repo/archive/refs/tags/v1.0.0.tar.gz"
            )

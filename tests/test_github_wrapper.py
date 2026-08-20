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

from src.registry_manager.github_wrapper import GitHubReleaseInfo, GithubWrapper
from src.registry_manager.version import Version


class TestGitHubReleaseInfo:
    """Test GitHubReleaseInfo class."""

    def test_strip_prefix_uses_commit_sha_not_branch_name(self) -> None:
        """Test that strip_prefix derives from commit SHA, not target_commitish.

        GitHub's tarball API produces archives with a top-level directory
        named '{owner}-{repo}-{short-sha}' where short-sha is the first
        7 characters of the *commit SHA*, not the branch name.

        If release.target_commitish is "main" (a branch), but the actual
        commit SHA is "9cda134abcdef...", the strip_prefix should use
        the commit SHA.
        """
        release_info = GitHubReleaseInfo(
            org_and_repo="eclipse-score/devcontainer",
            version=Version("1.0.0"),
            tag_name="v1.0.0",
            published_at=datetime(2024, 1, 1),
            prerelease=False,
            commit_sha="9cda134abcdef1234567890abcdef1234567890",
        )

        # The strip_prefix should be derived from commit_sha (9cda134)
        # NOT from a branch name like "main"
        assert release_info.strip_prefix == "eclipse-score-devcontainer-9cda134"
        assert "main" not in release_info.strip_prefix

    def test_tarball_url_uses_tag_name(self) -> None:
        """Test that tarball URL uses the tag name."""
        release_info = GitHubReleaseInfo(
            org_and_repo="org/repo",
            version=Version("1.2.3"),
            tag_name="v1.2.3",
            published_at=datetime(2024, 1, 1),
            prerelease=False,
            commit_sha="abcdef1234567890abcdef1234567890abcdef12",
        )

        assert (
            release_info.tarball
            == "https://api.github.com/repos/org/repo/tarball/v1.2.3"
        )


class TestGithubWrapper:
    """Test GithubWrapper class."""

    def test_get_latest_release_resolves_tag_to_commit_sha(self) -> None:
        """Test that get_latest_release resolves the tag to get the actual commit SHA.

        When fetching releases, release.target_commitish may be a branch name
        (e.g., "main"), not a commit SHA. We need to resolve the tag to get
        the actual commit SHA that GitHub's tarball API uses.

        Without this fix, the strip_prefix would be incorrect (using "main"
        instead of the 7-char commit SHA), causing Bazel extraction to fail
        because the archive's top-level directory won't match the expected
        strip_prefix.
        """
        # Create mock release object with branch name as target_commitish
        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.target_commitish = "main"  # This is a branch, not a commit SHA
        mock_release.published_at = datetime(2024, 1, 1)
        mock_release.prerelease = False

        # Mock commit object with the actual commit SHA
        mock_commit = MagicMock()
        mock_commit.sha = "9cda134abcdef1234567890abcdef1234567890"

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [mock_release]
        mock_repo.get_commit.return_value = mock_commit

        with patch.object(GithubWrapper, "__init__", lambda x, y: None):
            wrapper = GithubWrapper(None)
            wrapper.gh = MagicMock()  # type: ignore[attr-defined]
            wrapper.gh.get_repo.return_value = mock_repo  # type: ignore[union-attr]
            wrapper._release_cache = {}  # type: ignore[attr-defined]
            wrapper._module_file_cache = {}  # type: ignore[attr-defined]

            result = wrapper.get_latest_release("eclipse-score/devcontainer")  # type: ignore[attr-defined]

            # Verify that get_commit was called with the tag name
            mock_repo.get_commit.assert_called_once_with("v1.0.0")

            # Verify the returned release info has the correct commit SHA
            assert result is not None
            assert result.commit_sha == "9cda134abcdef1234567890abcdef1234567890"
            # NOT the branch name
            assert result.commit_sha != "main"

            # Verify that strip_prefix uses the commit SHA
            assert result.strip_prefix == "eclipse-score-devcontainer-9cda134"
            assert "main" not in result.strip_prefix

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

        # Mock commits
        old_commit = MagicMock()
        old_commit.sha = "0000000000000000000000000000000000000001"

        new_commit = MagicMock()
        new_commit.sha = "2222222222222222222222222222222222222222"

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = [older_release, newer_release]
        mock_repo.get_commit.side_effect = [old_commit, new_commit]

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
            assert result.commit_sha == "2222222222222222222222222222222222222222"

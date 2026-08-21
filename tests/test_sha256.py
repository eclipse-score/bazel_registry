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

import io
import tarfile
import urllib.request
from http.client import HTTPMessage

import pytest
from src.registry_manager.bazel_wrapper import (
    _archive_top_level_dir,  # pyright: ignore[reportPrivateUsage]
    _build_archive_request,  # pyright: ignore[reportPrivateUsage]
    _TokenSafeRedirectHandler,  # pyright: ignore[reportPrivateUsage]
    download_github_archive,
)

GITHUB_ARCHIVE_URL = "https://api.github.com/repos/org/repo/tarball/v1.0.0"


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data
        self._drained = False

    def read(self, _size: int = -1) -> bytes:
        if self._drained:
            return b""
        self._drained = True
        return self._data

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _make_targz(top_dir: str, files: dict[str, bytes] | None = None) -> bytes:
    """Build an in-memory .tar.gz whose entries live under ``top_dir``."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name=top_dir)
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
        for name, data in (files or {"README": b"hi"}).items():
            member = tarfile.TarInfo(name=f"{top_dir}/{name}")
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return buf.getvalue()


def _patch_opener(
    monkeypatch: pytest.MonkeyPatch,
    response_data: bytes,
    captured: dict[str, urllib.request.Request],
) -> None:
    def fake_open(
        self: urllib.request.OpenerDirector,
        req: urllib.request.Request,
        timeout: float | None = None,
    ) -> _FakeResp:
        captured["req"] = req
        return _FakeResp(response_data)

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)


class TestBuildArchiveRequest:
    """Test token handling when building the archive request."""

    def test_without_token_no_authorization_header(self) -> None:
        req = _build_archive_request(GITHUB_ARCHIVE_URL, token=None)
        assert not req.has_header("Authorization")

    def test_with_token_sends_bearer_header(self) -> None:
        req = _build_archive_request(GITHUB_ARCHIVE_URL, token="secret-token")
        assert req.has_header("Authorization")
        assert req.get_header("Authorization") == "Bearer secret-token"

    def test_rejects_token_for_non_github_host(self) -> None:
        with pytest.raises(ValueError, match="URL must use HTTPS and target"):
            _build_archive_request(
                "https://example.com/file.tar.gz", token="secret-token"
            )

    def test_rejects_token_over_plain_http(self) -> None:
        with pytest.raises(ValueError, match="URL must use HTTPS and target"):
            _build_archive_request(
                "http://github.com/org/repo/archive/refs/tags/v1.0.0.tar.gz",
                token="secret-token",
            )


class TestDownloadGithubArchive:
    """Test download_github_archive integrity + strip_prefix extraction."""

    def test_returns_integrity_and_strip_prefix_from_archive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A 40-char (private-repo style) SHA in the top-level dir, which the old
        # commit_sha[:7] guess would have gotten wrong.
        top_dir = "etas-eng-vsps_ids-ab76c9089eaa5f208daf6ffe6031ae9c87a460fd"
        payload = _make_targz(top_dir)
        captured: dict[str, urllib.request.Request] = {}
        _patch_opener(monkeypatch, payload, captured)

        integrity, strip_prefix = download_github_archive(GITHUB_ARCHIVE_URL)

        assert integrity.startswith("sha256-")
        assert strip_prefix == top_dir
        # No token passed -> no Authorization header on the wire.
        assert not captured["req"].has_header("Authorization")

    def test_sends_bearer_token_to_allowed_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = _make_targz("org-repo-1234567")
        captured: dict[str, urllib.request.Request] = {}
        _patch_opener(monkeypatch, payload, captured)

        download_github_archive(GITHUB_ARCHIVE_URL, token="secret-token")

        assert captured["req"].has_header("Authorization")
        assert captured["req"].get_header("Authorization") == "Bearer secret-token"

    def test_rejects_token_for_non_github_host(self) -> None:
        with pytest.raises(ValueError, match="URL must use HTTPS and target"):
            download_github_archive("https://example.com/file.tar.gz", token="t")


class TestArchiveTopLevelDir:
    """Test _archive_top_level_dir extraction."""

    def test_returns_single_top_level_dir(self) -> None:
        top_dir = "org-repo-deadbeef"
        payload = _make_targz(top_dir, {"src/main.py": b"print('hi')"})
        assert _archive_top_level_dir(io.BytesIO(payload)) == top_dir

    def test_rejects_multiple_top_level_dirs(self) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for d in ("a", "b"):
                info = tarfile.TarInfo(name=d)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
        buf.seek(0)
        with pytest.raises(
            ValueError, match="expected exactly one top-level directory"
        ):
            _archive_top_level_dir(buf)


def _redirect(from_url: str, to_url: str) -> urllib.request.Request:
    handler = _TokenSafeRedirectHandler()
    req = urllib.request.Request(from_url)
    req.add_header("Authorization", "Bearer secret-token")
    new_req = handler.redirect_request(
        req, io.BytesIO(), 302, "Found", HTTPMessage(), to_url
    )
    assert new_req is not None
    return new_req


def test_redirect_keeps_token_within_allowlist() -> None:
    new_req = _redirect(
        GITHUB_ARCHIVE_URL,
        "https://codeload.github.com/org/repo/tar.gz/refs/tags/v1.0.0",
    )
    assert new_req.get_header("Authorization") == "Bearer secret-token"


def test_redirect_strips_token_when_leaving_allowlist() -> None:
    new_req = _redirect(GITHUB_ARCHIVE_URL, "https://evil.example.com/steal")
    assert not new_req.has_header("Authorization")


def test_redirect_strips_token_on_downgrade_to_http() -> None:
    new_req = _redirect(GITHUB_ARCHIVE_URL, "http://github.com/org/repo/archive")
    assert not new_req.has_header("Authorization")

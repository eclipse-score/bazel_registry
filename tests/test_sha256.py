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
import urllib.request
from http.client import HTTPMessage

import pytest
from src.registry_manager.bazel_wrapper import (
    _TokenSafeRedirectHandler,  # pyright: ignore[reportPrivateUsage]
    sha256_from_url,
)

GITHUB_ARCHIVE_URL = "https://github.com/org/repo/archive/refs/tags/v1.0.0.tar.gz"


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


def _patch_opener(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, urllib.request.Request],
) -> None:
    def fake_open(
        self: urllib.request.OpenerDirector,
        req: urllib.request.Request,
        timeout: float | None = None,
    ) -> _FakeResp:
        captured["req"] = req
        return _FakeResp(b"hello")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)


def test_sha256_from_url_without_token_makes_unauthenticated_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, urllib.request.Request] = {}
    _patch_opener(monkeypatch, captured)

    result = sha256_from_url("https://example.com/file.tar.gz")

    assert result.startswith("sha256-")
    assert not captured["req"].has_header("Authorization")


def test_sha256_from_url_with_token_sends_bearer_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, urllib.request.Request] = {}
    _patch_opener(monkeypatch, captured)

    sha256_from_url(GITHUB_ARCHIVE_URL, token="secret-token")

    assert captured["req"].has_header("Authorization")
    assert captured["req"].get_header("Authorization") == "Bearer secret-token"


def test_sha256_from_url_rejects_token_for_non_github_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, urllib.request.Request] = {}
    _patch_opener(monkeypatch, captured)

    with pytest.raises(ValueError, match="URL must use HTTPS and target"):
        sha256_from_url("https://example.com/file.tar.gz", token="secret-token")

    assert "req" not in captured  # no request was ever opened


def test_sha256_from_url_rejects_token_over_plain_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, urllib.request.Request] = {}
    _patch_opener(monkeypatch, captured)

    with pytest.raises(ValueError, match="URL must use HTTPS and target"):
        sha256_from_url(
            "http://github.com/org/repo/archive/refs/tags/v1.0.0.tar.gz",
            token="secret-token",
        )

    assert "req" not in captured


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

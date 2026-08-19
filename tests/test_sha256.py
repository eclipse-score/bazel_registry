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

from unittest.mock import patch

from src.registry_manager.bazel_wrapper import sha256_from_url


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data
        self._drained = False

    def read(self, _size: int = -1) -> bytes:
        if self._drained:
            return b""
        self._drained = True
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_sha256_from_url_without_token_makes_unauthenticated_request():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return _FakeResp(b"hello")

    with patch(
        "src.registry_manager.bazel_wrapper.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        result = sha256_from_url("https://example.com/file.tar.gz")

    assert result.startswith("sha256-")
    assert not captured["req"].has_header("Authorization")


def test_sha256_from_url_with_token_sends_bearer_header():
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return _FakeResp(b"hello")

    with patch(
        "src.registry_manager.bazel_wrapper.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        sha256_from_url("https://example.com/file.tar.gz", token="secret-token")

    assert captured["req"].has_header("Authorization")
    assert captured["req"].get_header("Authorization") == "Bearer secret-token"

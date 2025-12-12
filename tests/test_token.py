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

import subprocess
from argparse import Namespace
from unittest.mock import patch

from src.registry_manager.main import get_token


class TestGitHubTokenResolution:
    """Test GitHub token resolution."""

    def test_token_from_cli_argument(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env_token"}):
            args = Namespace(github_token="cli_token")
            assert get_token(args) == "cli_token"

    def test_token_from_environment(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env_token"}):
            args = Namespace(github_token=None)
            assert get_token(args) == "env_token"

    def test_token_fallback_when_unavailable(self):
        with patch.dict("os.environ", {}, clear=True):
            args = Namespace(github_token=None)
            with patch(
                "subprocess.check_output",
                side_effect=subprocess.CalledProcessError(1, "gh"),
            ):
                assert get_token(args) is None

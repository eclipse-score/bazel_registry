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

from src.registry_manager.main import parse_args


class TestArgumentParsing:
    """Test command-line argument parsing."""

    def test_parse_args_no_arguments(self):
        args = parse_args([])
        assert args.github_token is None
        assert args.modules == []

    def test_parse_args_with_token(self):
        args = parse_args(["--github-token", "mytoken123"])
        assert args.github_token == "mytoken123"

    def test_parse_args_with_module_names(self):
        args = parse_args(["score_alpha", "score_beta"])
        assert args.modules == ["score_alpha", "score_beta"]

    def test_parse_args_with_token_and_modules(self):
        args = parse_args(["--github-token", "token123", "score_alpha", "score_beta"])
        assert args.github_token == "token123"
        assert args.modules == ["score_alpha", "score_beta"]

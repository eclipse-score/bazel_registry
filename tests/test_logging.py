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

import pytest
from src.registry_manager.gh_logging import Logger


def test_debug_messages_are_printed_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    Logger("test").debug("shown")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "DEBUG: test shown" in captured.err

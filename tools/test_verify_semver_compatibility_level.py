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
import json
from pathlib import Path
from typing import Any

from .verify_semver_compatibility_level import analyze


def build_fake_filesystem(fs: Any, structure: dict[str, object], base_path: str = ""):
    """See examples below to understand the dict structure."""
    for name, value in structure.items():
        path = f"{base_path}/{name}"
        if isinstance(value, dict):
            fs.makedirs(path, exist_ok=True)
            build_fake_filesystem(fs, value, path)
        else:
            fs.create_file(path, contents=value)


def test_all_correct(fs: Any):
    """When all modules have compatibility_level matching major version, all is well."""
    build_fake_filesystem(fs, {
        "modules": {
            "a_correct_module": {
                "metadata.json": '{"versions": ["1.0.0", "2.0.0"]}',
                "1.0.0": {"MODULE.bazel": "module(name='a_correct_module', version='1.0.0', compatibility_level=1)\n"},
                "2.0.0": {"MODULE.bazel": "module(name='a_correct_module', version='2.0.0', compatibility_level=2)\n"},
            }
        }
    })
    results = analyze(Path("/modules"))
    assert results[0].type == "ok"
    assert results[1].type == "ok"
    assert len(results) == 2


def test_missing_level(fs: Any):
    """Missing compatibility_level should not fail, but warn."""
    build_fake_filesystem(fs, {
        "modules": {
            "bar": {
                "metadata.json": json.dumps({"versions": ["1.0.0"]}),
                "1.0.0": {"MODULE.bazel": "module(name='bar', version='1.0.0')\n"},
            }
        }
    })
    results = analyze(Path("/modules"))
    assert results[0].type == "warning"
    assert len(results) == 1


def test_wrong_level(fs: Any):
    """When compatibility_level does not match major version, it should fail."""
    build_fake_filesystem(fs, {
        "modules": {
            "a_wrong_module": {
                "metadata.json": '{"versions": ["1.0.0"]}',
                "1.0.0": {"MODULE.bazel": "module(name='a_wrong_module', version='1.0.0', compatibility_level=2)\n"},
            }
        }
    })
    results = analyze(Path("/modules"))
    assert results[0].type == "error"
    assert len(results) == 1

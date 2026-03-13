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

from src.registry_manager.bazel_wrapper import parse_MODULE_file_content


class TestModuleFileParsing:
    """Test parsing MODULE.bazel content."""

    def test_parse_complete_module_file(self):
        content = 'module(name="score_demo", version="1.2.3", compatibility_level=2)'
        parsed = parse_MODULE_file_content(content)
        assert str(parsed.version) == "1.2.3"
        assert parsed.comp_level == 2
        assert parsed.major_version == 1  # major version is first digit of version

    def test_parse_minimal_module_file(self):
        content = 'module(name="score_demo")'
        parsed = parse_MODULE_file_content(content)
        assert parsed.version is None
        assert parsed.comp_level is None
        assert parsed.major_version is None

    def test_parse_module_file_content_preserved(self):
        content = 'module(name="test", version="1.0.0")\nbazel_dep(...)'
        parsed = parse_MODULE_file_content(content)
        assert parsed.content == content

    def test_parse_ignores_bazel_dep_version(self):
        """version= in bazel_dep() must not be confused with the module version."""
        content = 'module(name = "score_demo")\nbazel_dep(name = "platforms", version = "1.0.0")'
        parsed = parse_MODULE_file_content(content)
        assert parsed.version is None
        assert parsed.comp_level is None

    def test_parse_multiline_module_call(self):
        """Multiline module() call is parsed correctly."""
        content = (
            'module(\n'
            '    name = "score_demo",\n'
            '    version = "2.0.0",\n'
            '    compatibility_level = 2,\n'
            ')\n'
            'bazel_dep(name = "platforms", version = "0.1.0")\n'
        )
        parsed = parse_MODULE_file_content(content)
        assert str(parsed.version) == "2.0.0"
        assert parsed.comp_level == 2

    def test_parse_zero_version(self):
        """Version 0.0.0 and compatibility_level 0 are parsed correctly."""
        content = 'module(name="score_demo", version="0.0.0", compatibility_level=0)'
        parsed = parse_MODULE_file_content(content)
        assert str(parsed.version) == "0.0.0"
        assert parsed.comp_level == 0
        assert parsed.major_version == 0

    def test_parse_version_without_comp_level(self):
        """version= present but no compatibility_level= → comp_level is None."""
        content = 'module(name="score_demo", version="0.0.0")'
        parsed = parse_MODULE_file_content(content)
        assert str(parsed.version) == "0.0.0"
        assert parsed.comp_level is None

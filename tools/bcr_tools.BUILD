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

# This file replaces the original BUILD file, as it does not expose bcr_validation
# as a py_library.

load("@pip//:requirements.bzl", "all_requirements")
load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "bcr",
    srcs = glob(["tools/*.py"]),
    deps = all_requirements,
    # we must allow imports from the tools directory, as the scripts
    # import eachother simply by filename.
    imports = ["tools"],
    visibility = ["//visibility:public"],
)

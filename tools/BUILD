# *******************************************************************************
# Copyright (c) 2024 Contributors to the Eclipse Foundation
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

load("@rules_python//python:pip.bzl", "compile_pip_requirements")
load("@rules_python//python:defs.bzl", "py_binary")
load("@pip//:requirements.bzl", "all_requirements")

load("@score_cr_checker//:cr_checker.bzl", "copyright_checker")
load("@score_dash_license_checker//:dash.bzl", "dash_license_checker")
load("@score_python_basics//:defs.bzl", "score_virtualenv")

copyright_checker(
    name = "copyright",
    srcs = glob(["*"]),
    template = "@score_cr_checker//resources:templates",
    config = "@score_cr_checker//resources:config",
    visibility = ["//visibility:public"],
)

dash_license_checker(
    src = "//tools:requirements.txt",
    file_type = "requirements",
    visibility = ["//visibility:public"],
)

compile_pip_requirements(
    name = "requirements",
    srcs = [
        ":requirements.in",
        "@score_python_basics//:requirements.txt",
    ],
    requirements_txt = "requirements.txt",
)

score_virtualenv(
    reqs=all_requirements + ["@bazel_central_registry//:bcr"],
)

py_binary(
    name="verify_modules",
    srcs=["verify_modules.py"],
    deps=all_requirements + ["@bazel_central_registry//:bcr"],
)

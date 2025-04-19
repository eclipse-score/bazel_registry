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

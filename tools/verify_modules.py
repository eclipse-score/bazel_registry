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

import os
import sys
from typing import Any

import bcr_validation


def patch_bcr_validation():
    # Print icons, instead of colors.
    # This way it's readable in any unicode terminal, including GitHub Actions.
    bcr_validation.COLOR = {
        bcr_validation.BcrValidationResult.GOOD: "✅ ",
        bcr_validation.BcrValidationResult.NEED_BCR_MAINTAINER_REVIEW: "⚠️ ",
        bcr_validation.BcrValidationResult.FAILED: "❌ ",
    }
    # No need to reset color, since we don't use colors.
    bcr_validation.RESET = ""

    # '--skip_validation presubmit_yml' doesn't quite do what it promises.
    # It skips execution, but not validation of the file.
    # As we do not use presubmit.yml, we don't want to validate it at all.
    bcr_validation.BcrValidator.validate_presubmit_yml = lambda *_: None # type: ignore


def get_workspace_dir():
    if workspace_dir := os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
        # `bazel run //tools:verify_modules`
        return workspace_dir
    else:
        # `bazel-bin/tools/verify_modules`
        return os.getcwd()


def main():
    patch_bcr_validation()

    args = [
        "--registry",
        get_workspace_dir(),
        "--check_all",

        # For now skip the validation of the URL stability.
        "--skip_validation",
        "url_stability",

        # Skip validation of presubmit.yml as we don't use that approach.
        "--skip_validation",
        "presubmit_yml",
    ]
    return bcr_validation.main(args)


if __name__ == "__main__":
    sys.exit(main())

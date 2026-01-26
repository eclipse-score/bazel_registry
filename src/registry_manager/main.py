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

import argparse
import os
import subprocess
import sys

from . import ModuleUpdateInfo
from .bazel_wrapper import (
    BazelModuleInfo,
    ModuleUpdateRunner,
    parse_MODULE_file_content,
    read_modules,
)
from .gh_logging import Logger
from .github_wrapper import GithubWrapper

log = Logger(__name__)


def parse_args(args: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check and update modules to latest releases."
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=None,
        help=(
            "GitHub token for accessing the GitHub API (avoids rate limits); "
            "defaults to $GITHUB_TOKEN or `gh auth token`."
        ),
    )
    parser.add_argument(
        "modules",
        nargs="*",
        help="If not provided, all modules are processed according to their "
        "periodic-pull setting. Otherwise the provided modules are processed.",
    )
    return parser.parse_args(args)


def get_token(args: argparse.Namespace) -> str | None:
    """Get GitHub API token from CLI, environment, or gh CLI tool.

    Tries sources in order:
    1. --github-token CLI argument
    2. GITHUB_TOKEN environment variable
    3. Output of `gh auth token`
    """
    if args.github_token:
        log.debug("Using GitHub token from command-line argument.")
        return args.github_token
    elif token := os.getenv("GITHUB_TOKEN"):
        log.debug("Using GitHub token from environment variable.")
        return token
    else:
        try:
            token = (
                subprocess.check_output(["gh", "auth", "token"]).decode("utf-8").strip()
            )
            log.debug("Using GitHub token from `gh auth token`.")
            return token
        except subprocess.CalledProcessError:
            log.debug("No GitHub token provided; proceeding without one.")
            return None


def plan_module_updates(
    args: argparse.Namespace,
    gh: GithubWrapper,
    modules_to_check: list[BazelModuleInfo],
) -> list[ModuleUpdateInfo]:
    """Plan module updates based on latest GitHub releases.

    Checks each module for new releases and builds an update plan.
    """
    updated_modules: list[ModuleUpdateInfo] = []

    for module in modules_to_check:
        # Skip non-periodic modules unless explicitly requested
        if not module.periodic_pull and not args.modules:
            log.info(f"Skipping module {module.name} as periodic-pull is false")
            continue

        log.debug(f"Checking module {module.name}...")

        latest_release = gh.get_latest_release(module.org_and_repo)
        if latest_release and module.latest_version != latest_release.version:
            if not latest_release.version.semver:
                # In the future we can extend non-semver handling if needed
                log.warning(
                    f"Latest release {latest_release.version} of "
                    f"{module.name} is not a valid semantic version; skipping."
                )
                continue

            log.info(
                f"Updating {module.name} "
                f"from {module.latest_version} to {latest_release.version}"
            )
            content = gh.try_get_module_file_content(
                module.org_and_repo, str(latest_release.tag_name)
            )

            if content:
                module_file_content = parse_MODULE_file_content(content)
                updated_modules.append(
                    ModuleUpdateInfo(
                        module=module,
                        release=latest_release,
                        mod_file=module_file_content,
                    )
                )
            else:
                log.warning(
                    f"Could not retrieve MODULE.bazel for "
                    f"{module.name} at tag {latest_release.tag_name}; skipping."
                )
        else:
            log.info(f"Module {module.name} is up to date.")

    if not updated_modules:
        log.info("No modules need updating.")
    else:
        log.debug(f"Modules to be updated: {[m.module.name for m in updated_modules]}")

    return updated_modules


def main(args: list[str]) -> None:
    """Main entry point for the registry manager.

    Reads modules, checks for updates on GitHub, and generates update files.
    """
    p = parse_args(args)
    modules = read_modules(p.modules)
    gh = GithubWrapper(get_token(p))
    plan = plan_module_updates(p, gh, modules)

    for task in plan:
        log.info(
            f"Module {task.module.name} should be updated to "
            f"{task.release.version} from {task.module.latest_version}"
        )
        ModuleUpdateRunner(task).generate_files()

    if log.warnings:
        # If any warnings were issued, exit with non-zero code
        log.fatal(f"Completed with {len(log.warnings)} warnings.")


if __name__ == "__main__":
    main(args=sys.argv[1:])

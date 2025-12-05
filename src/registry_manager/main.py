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
import difflib
import os
import string
import subprocess
import sys

from registry_manager import gh_logging
from registry_manager.bazel_files import (
    ModuleInfo,
    add_version,
    parse_MODULE_file_content,
    read_modules,
)
from registry_manager.github_wrapper import GithubWrapper

log = gh_logging.MyLog()


def parse_args(args: list[str]):
    parser = argparse.ArgumentParser(
        description="Check and update modules to latest releases."
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub token for accessing the GitHub API (to avoid rate limits).",
    )
    parser.add_argument(
        "--force_update_all",
        action="store_true",
        help="Check all modules, even those without periodic-pull set.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update all modules (with periodic-pull set) to latest releases.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run checks to verify integrity of bazel_registry.",
    )
    parser.add_argument(
        "modules",
        nargs="*",
        help="If not provided, all modules are processed.",
    )
    return parser.parse_args(args)


def render_text_representation(s: str) -> str:
    out = []
    for ch in s:
        if ch == "\n":
            out.append("⏎\n")  # mark newline
        elif ch == "\r":
            out.append("␍")  # carriage return
        elif ch == " ":
            out.append("·")  # visualize space
        elif ch == "\t":
            out.append("→")  # visualize tab
        elif ch in string.printable:
            out.append(ch)
        else:
            out.append(f"\\x{ord(ch):02x}")  # non-printable
    return "".join(out)


def generate_text_diff(a: str, b: str, a_name: str, b_name: str):
    a_v = render_text_representation(a).splitlines(keepends=True)
    b_v = render_text_representation(b).splitlines(keepends=True)

    diff = difflib.unified_diff(
        a_v,
        b_v,
        fromfile=a_name,
        tofile=b_name,
    )
    return "".join(diff)


def get_token(args: argparse.Namespace) -> str | None:
    if args.github_token:
        log.debug("Using GitHub token from command-line argument.")
        return args.github_token
    elif token := os.getenv("GITHUB_TOKEN"):
        log.debug("Using GitHub token from environment variable.")
        return token
    else:
        # try running `gh auth token`
        try:
            token = (
                subprocess.check_output(["gh", "auth", "token"]).decode("utf-8").strip()
            )
            log.debug("Using GitHub token from `gh auth token`.")
            return token
        except Exception:
            log.debug("No GitHub token provided; proceeding without one.")
            return None


def update_modules(
    args: argparse.Namespace, gh: GithubWrapper, modules_to_check: list[ModuleInfo]
):
    updated_modules: list[ModuleInfo] = []

    for module in modules_to_check:
        if not module.periodic_pull and not args.force_update_all and not args.modules:
            log.info(f"Skipping module {module.name} as periodic-pull is false")
            continue

        log.debug(f"Checking module {module.name}...")

        latest_release = gh.get_latest_release(module.org_and_repo)
        if latest_release and module.latest_version != latest_release.version:
            log.info(
                f"Updating {module.name} "
                f"from {module.latest_version} to {latest_release.version}"
            )
            remote_content = gh.try_get_module_file_content(
                module.org_and_repo, latest_release.version
            )
            if remote_content:
                add_version(
                    module=module,
                    new_version=latest_release.version,
                    tarball=latest_release.tarball,
                    bazel_module_file_content=remote_content,
                )
                updated_modules.append(module)
        else:
            log.info(f"Module {module.name} is up to date.")

    if not updated_modules:
        log.info("No modules were updated.")

    return updated_modules


def check_modules(
    args: argparse.Namespace, gh: GithubWrapper, modules_to_check: list[ModuleInfo]
):
    """Note: checks are only performed on the last 3 versions of each module."""

    def warn(msg: str):
        log.warning(f"{module.name} @ {version}: {msg}", file=file)

    for module in modules_to_check:
        log.debug(f"Checking module {module.name}...")

        for version in module.versions[-3:]:
            log.debug(f" Checking version {version}...")
            file = module.path / version / "MODULE.bazel"
            local_content = file.read_text()
            remote_content = gh.try_get_module_file_content(
                module.org_and_repo, version
            )
            if remote_content is None:
                warn("could not fetch remote MODULE.bazel file. Tag named incorrectly?")
            elif local_content != remote_content:
                diff = generate_text_diff(
                    local_content,
                    remote_content,
                    "bazel_registry",
                    f"remote at {module.org_and_repo}@v{version}",
                )
                warn("local MODULE.bazel does not match remote MODULE.bazel:\n" + diff)

            data = parse_MODULE_file_content(local_content)
            if data.version != version:
                warn(f"declared version '{data.version}'.")

            if data.compatibility_level is None:
                warn(
                    "missing compatibility_level field "
                    f"(set to {data.major_version} <major_version>)."
                )

            elif data.major_version != data.compatibility_level:
                warn(
                    f"compatibility_level "
                    f"({data.compatibility_level}) does not match "
                    f"major version ({data.major_version})."
                )


def main(args: list[str]):
    p = parse_args(args)
    gh = GithubWrapper(get_token(p))
    modules = read_modules(p.modules)

    if p.update:
        _updated_modules = update_modules(p, gh, modules)
    elif p.check:
        check_modules(p, gh, modules)
    else:
        log.fatal("Either --update or --check must be specified.")

    if log.warnings > 0:
        # If any warnings were issued, exit with non-zero code
        log.fatal(f"Completed with {log.warnings} warnings.")


if __name__ == "__main__":
    main(args=sys.argv[1:])

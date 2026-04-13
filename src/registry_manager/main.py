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
import json
import os
import subprocess
import sys
from dataclasses import dataclass

from . import ModuleUpdateInfo
from .bazel_wrapper import (
    BazelModuleInfo,
    ModuleUpdateRunner,
    parse_MODULE_file_content,
    read_modules,
)
from .gh_logging import Logger
from .github_wrapper import GithubWrapper
from .version import Version

log = Logger(__name__)


@dataclass(frozen=True)
class RegistryRunResult:
    updated_modules: list[ModuleUpdateInfo]
    warnings: list[str]

    @property
    def has_updates(self) -> bool:
        return bool(self.updated_modules)

    @property
    def commit_msg(self) -> str | None:
        if not self.updated_modules:
            return None

        if len(self.updated_modules) == 1:
            update = self.updated_modules[0]
            return f"feat: update {update.module.name} to {update.release.version}"

        title = "feat: update multiple modules"
        lines = [
            f"- {update.module.name} -> {update.release.version}"
            for update in self.updated_modules
        ]
        return title + "\n\n" + "\n".join(lines)

    @property
    def pr_title(self) -> str:
        if self.commit_msg:
            return self.commit_msg.splitlines()[0]
        return "Update modules"

    def _generate_report(self) -> str:
        lines = []
        if not self.updated_modules:
            lines.append("All modules are up to date; no updates needed.")
        else:
            lines.append(f"Updated {len(self.updated_modules)} module(s):")
            lines.extend(
                (
                    f"- {u.module.name}: {u.module.latest_version} -> {u.release.version}"
                    if u.module.versions
                    else f"- {u.module.name}: add {u.release.version}"
                )
                for u in self.updated_modules
            )

        if self.warnings:
            lines.append("")
            lines.append(f"{len(self.warnings)} warning(s):")
            for w in self.warnings:
                lines.append(f"- {w}")

        return "\n".join(lines)

    @property
    def pr_body(self) -> str:
        return """This PR updates the modules to their latest versions.
Please review and merge if everything looks good.

""" + self._generate_report()

    def _get_outputs(self) -> dict[str, object]:
        outputs: dict[str, object] = {"has_updates": self.has_updates}
        if self.has_updates:
            outputs.update(
                {
                    "commit_msg": self.commit_msg,
                    "pr_title": self.pr_title,
                    "pr_body": self.pr_body,
                }
            )
        return outputs

    def render(self, mode: str | None) -> str:
        if not mode:  # cli by default
            return self._generate_report()

        outputs = self._get_outputs()
        if mode == "json":
            return json.dumps(outputs, indent=2) + "\n"
        else:  # github_output
            return "".join(_format_github_output(k, v) for k, v in outputs.items())


def _format_github_output(name: str, value: object) -> str:
    """Format a GitHub Actions output variable according to the rules in
    https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#about-yaml-syntax-for-github-actions
    """

    if isinstance(value, bool):
        return f"{name}={'true' if value else 'false'}\n"

    text = json.dumps(value, indent=2) if isinstance(value, list | dict) else str(value)

    if "\n" not in text:
        return f"{name}={text}\n"
    else:
        delimiter = "EOF"
        # Make the delimiter unique
        while delimiter in text:
            delimiter += "_X"
        return f"{name}<<{delimiter}\n{text}\n{delimiter}\n"


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
    parser.add_argument(
        "--format",
        choices=["json", "github_output"],
        default=None,
        help=(
            "Output format. 'json' emits a single JSON object on stdout. "
            "'github_output' emits GitHub Actions output syntax on stdout. "
            "All diagnostics are written to stderr."
        ),
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


def is_release_semver_acceptable(module: BazelModuleInfo, new_version: Version) -> bool:
    """
    Verify that a new release version follows semantic versioning expectations.

    Returns True if the new version is acceptable, False otherwise.

    See tests for details on what is "acceptable".
    """
    if not new_version.semver:
        log.warning(
            f"Latest release {new_version} of "
            f"{module.name} is not a valid semantic version."
        )
        # Cannot derive any semantic versioning rules.
        # In the future we can extend non-semver handling if needed.
        return False

    # Check if the exact version already exists
    if new_version in module.versions:
        log.warning(
            f"Latest release {new_version} of {module.name} "
            f"already exists in the registry; it will be skipped."
        )
        return False

    semver_versions = [v.semver for v in module.versions if v.semver]

    # Check for backwards prerelease/build variants within the same base version
    same_base = [
        v
        for v in semver_versions
        if v.major == new_version.semver.major
        and v.minor == new_version.semver.minor
        and v.patch == new_version.semver.patch
    ]
    if same_base:
        max_same_base = max(same_base)
        if new_version.semver < max_same_base:
            log.warning(
                f"Latest release {new_version} of {module.name} "
                f"is a backwards prerelease/build variant of {max_same_base}; it will be skipped."
            )
            return False

    # Check for backwards patch versions within the same major.minor series
    same_major_minor = [
        v
        for v in semver_versions
        if v.major == new_version.semver.major and v.minor == new_version.semver.minor
    ]

    if same_major_minor:
        max_patch = max(v.patch for v in same_major_minor)
        if new_version.semver.patch < max_patch:
            log.warning(
                f"Latest release {new_version} of {module.name} "
                f"is a backwards patch version (highest is *.*.{max_patch}); it will be skipped."
            )
            return False

    return True


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
            log.debug(f"Skipping module {module.name} as periodic-pull is false")
            continue

        log.debug(f"Checking module {module.name}...")

        latest_release = gh.get_latest_release(module.org_and_repo)

        if not latest_release:
            log.debug(
                f"No releases found for {module.name} at "
                f"{module.org_and_repo}; skipping."
            )
        elif latest_release.version not in module.versions:
            # TODO: this check belongs into local release workflows and not into bazel_registry.
            if not is_release_semver_acceptable(module, latest_release.version):
                # is_release_semver_acceptable already printed a warning
                continue

            if module.versions:
                log.debug(
                    f"Updating {module.name} "
                    f"from {module.latest_version} to {latest_release.version}"
                )
            else:
                log.debug(
                    f"Adding first version to {module.name}: {latest_release.version}"
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
            log.debug(f"Module {module.name} is up to date ({module.latest_version}).")

    if not updated_modules:
        log.debug("No modules need updating.")
    else:
        log.debug(f"Modules to be updated: {[m.module.name for m in updated_modules]}")

    return updated_modules


def apply_updates(plan: list[ModuleUpdateInfo]) -> None:
    for task in plan:
        if task.module.versions:
            log.debug(
                f"Updating {task.module.name} "
                f"from {task.module.latest_version} to {task.release.version}"
            )
        else:
            log.debug(
                f"Adding first version to {task.module.name}: {task.release.version}"
            )
        ModuleUpdateRunner(task).generate_files()

    if not plan:
        log.debug("All modules are up to date; no updates needed.")


def main(args: list[str]) -> None:
    """Main entry point for the registry manager.

    Reads modules, checks for updates on GitHub, and generates update files.
    """
    log.clear()  # currently log is a global singleton. At least we need to clear it.

    p = parse_args(args)
    modules = read_modules(p.modules)
    gh = GithubWrapper(get_token(p))

    # 1. Plan updates
    plan = plan_module_updates(p, gh, modules)

    # 2. Perform updates
    apply_updates(plan)

    # 3. Construct result
    result = RegistryRunResult(
        updated_modules=plan,
        warnings=Logger.warning_messages(),
    )

    # 4. Output result in requested format
    print(result.render(p.format))

    if result.warnings:
        # If any warnings were issued, exit with non-zero code
        log.fatal(f"Completed with {len(result.warnings)} warnings.")


def cli() -> None:
    main(args=sys.argv[1:])


if __name__ == "__main__":
    cli()

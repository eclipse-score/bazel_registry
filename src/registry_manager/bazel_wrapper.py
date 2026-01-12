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

import base64
import difflib
import hashlib
import json
import re
import urllib.request
from collections.abc import Iterable
from pathlib import Path

from . import (
    BazelModuleInfo,
    ModuleFileContent,
    ModuleUpdateInfo,
    Version,
)
from .gh_logging import Logger

log = Logger(__name__)


def _parse_versions(raw_versions: object, metadata_path: Path) -> list[Version]:
    """Validate and sort a list of semantic version strings."""
    if raw_versions is None:
        return []

    if not isinstance(raw_versions, list):
        log.fatal(
            f"{metadata_path} has invalid versions field; expected list of semantic version strings",
            file=metadata_path,
        )

    versions: list[Version] = [Version(v) for v in raw_versions]  # pyright: ignore[reportUnknownVariableType]

    # Sort in descending order (highest version first)
    return sorted(
        versions,
        reverse=True,
    )


def read_modules(module_names: list[str] | None) -> list[BazelModuleInfo]:
    """Load modules from the registry."""
    modules: list[BazelModuleInfo] = []
    if module_names:
        for module_name in module_names:
            metadata_path = Path("modules") / module_name / "metadata.json"
            if m := try_parse_metadata_json(metadata_path):
                if not m.obsolete:
                    modules.append(m)
            else:
                log.fatal(f"Module '{module_name}' could not be found or parsed.")
    else:
        for module_dir in Path("modules").iterdir():
            if m := try_parse_metadata_json(module_dir / "metadata.json"):  # noqa: SIM102
                if not m.obsolete:
                    modules.append(m)
    return modules


def try_parse_metadata_json(metadata_json: Path) -> BazelModuleInfo | None:
    """Parse a module metadata.json file."""
    module_path = metadata_json.parent
    if not module_path.is_dir():
        return None

    if not metadata_json.exists():
        log.warning(f"{metadata_json} does not exist; skipping")
        return None

    if not module_path.name.startswith("score_"):
        log.warning(f"{module_path} is not prefixed with 'score_'", file=metadata_json)

    try:
        with open(metadata_json) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"{metadata_json} could not be parsed: {e}")
        return None

    if (
        "repository" not in data
        or not isinstance(data["repository"], list)
        or len(data["repository"]) != 1
    ):
        log.warning(
            f"{metadata_json} has invalid repository field; expected one element",
            file=metadata_json,
        )
        return None

    repo = data["repository"][0]
    if not isinstance(repo, str) or not repo.startswith("github:"):
        log.warning(
            f"{metadata_json} has non-GitHub repository '{repo}'; skipping",
            file=metadata_json,
        )
        return None

    versions = _parse_versions(data.get("versions", []), metadata_json)

    return BazelModuleInfo(
        path=metadata_json.parent,
        name=metadata_json.parent.name,
        org_and_repo=repo[len("github:") :],
        versions=versions,
        periodic_pull=bool(data.get("periodic-pull", False)),
        obsolete=bool(data.get("obsolete", False)),
    )


def parse_MODULE_file_content(content: str) -> ModuleFileContent:
    """Parse the content of a MODULE.bazel file.

    Extracts version and compatibility_level using regex patterns.
    """
    comp_level = None
    if m_cl := re.search(r"compatibility_level\s*=\s*(\d+)", content):
        comp_level = int(m_cl.group(1))

    version = None
    if m_ver := re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", content):
        version = str(m_ver.group(1))

    return ModuleFileContent(
        content=content,
        comp_level=comp_level,
        version=Version(version) if version else None,
    )


def _sha256_from_bytes(stream: Iterable[bytes]) -> str:
    """Compute SHA256 hash from byte chunks and return as base64.

    Returns format: "sha256-<base64_encoded_hash>"
    """
    h = hashlib.sha256()
    for chunk in stream:
        h.update(chunk)
    raw = h.digest()
    b64 = base64.b64encode(raw).decode("ascii")
    return "sha256-" + b64


def sha256_from_url(url: str) -> str:
    """Download file from URL and compute its SHA256 hash."""
    with urllib.request.urlopen(url, timeout=10) as resp:

        def chunk_iter():
            while chunk := resp.read(1024 * 1024):
                yield chunk

        return _sha256_from_bytes(chunk_iter())


def sha256_from_string(content: str) -> str:
    """Compute SHA256 hash from a string."""
    return _sha256_from_bytes([content.encode("utf-8")])


class ModuleUpdateRunner:
    """Generates registry files for a module update.

    Creates or updates metadata.json, MODULE.bazel, patches/, and source.json
    for a module version.
    """

    def __init__(self, task_info: ModuleUpdateInfo):
        self.info = task_info
        self.patches: dict[str, str] = {}
        self.module_path = Path("modules") / task_info.module.name
        self.module_version_path = self.module_path / str(task_info.release.version)

    def generate_files(self) -> None:
        """Generate all necessary registry files for this module update.

        Creates:
        - Updated metadata.json with new version
        - MODULE.bazel file (with version patch if needed)
        - patches/ directory with any necessary patches
        - source.json with integrity hash and patch metadata
        """
        self._add_version_to_metadata()
        patched_module_file = self._create_patch_for_module_version_if_mismatch()
        self._generate_source_json()
        self._write_files(patched_module_file)

    def _generate_source_json(self) -> None:
        """Generate source.json with integrity hash and patch metadata."""
        repo = self.info.module.org_and_repo.split("/")[-1]
        integrity = sha256_from_url(self.info.release.tarball)
        source_dict: dict[str, object] = {
            "integrity": integrity,
            "strip_prefix": f"{repo}-{self.info.release.version}",
            "url": self.info.release.tarball,
        }

        if self.patches:
            source_dict["patch_strip"] = 1
            source_dict["patches"] = {
                patch_name: sha256_from_string(patch_text)
                for patch_name, patch_text in self.patches.items()
            }

        self.module_version_path.mkdir(parents=True, exist_ok=True)
        with open(self.module_version_path / "source.json", "w") as f:
            json.dump(source_dict, f, indent=4)
            f.write("\n")

    def _add_version_to_metadata(self) -> None:
        """Add the new version to metadata.json and keep versions sorted."""
        metadata_path = self.module_path / "metadata.json"
        with open(metadata_path, "r+") as f:
            metadata = json.load(f)
            versions = _parse_versions(metadata.get("versions", []), metadata_path)

            if self.info.release.version in versions:
                raise RuntimeError(
                    f"Version {self.info.release.version} already present in metadata"
                    f" for module {self.info.module.name}"
                )

            # prepend new version. This way we always modify a single line.
            # (otherwise a comma needs to be added to the previous last line)
            metadata["versions"] = [str(self.info.release.version)] + [
                str(v) for v in versions
            ]
            f.seek(0)
            f.truncate()
            json.dump(metadata, f, indent=4)
            f.write("\n")

    def _write_files(self, patched_module_file: str | None) -> None:
        """
        Write MODULE.bazel and patches to disk.

        Note: if patched_module_file is provided, it is written as MODULE.bazel;
        otherwise, the original module file content is used.
        """
        if not self.info.mod_file:
            raise ValueError("Module file content not available")

        self.module_version_path.mkdir(parents=True, exist_ok=True)
        with open(self.module_version_path / "MODULE.bazel", "w") as f:
            if patched_module_file:
                f.write(patched_module_file)
            else:
                f.write(self.info.mod_file.content)

        patches_dir = self.module_version_path / "patches"
        patches_dir.mkdir(exist_ok=True)
        for patch_name, patch_text in self.patches.items():
            with open(patches_dir / patch_name, "w") as pf:
                pf.write(patch_text)

    def _create_patch_for_module_version_if_mismatch(self) -> str | None:
        """Create a patch if MODULE.bazel version doesn't match release version.

        If the downloaded MODULE.bazel declares a different version or
        compatibility_level than the release, a patch is created to stamp
        the correct version.

        Note: this is based on rather fragile regex replacements and may need
        adjustments for more complex MODULE.bazel files.
        Example that would fail:
        # module(this_is_just_a_comment, version='1.0.0', compatibility_level=1)
        module(real_module)
        """
        if not self.info.mod_file:
            raise ValueError("Module file content not available")

        # Check if no patch is needed
        if (
            self.info.mod_file.version == self.info.release.version
            and self.info.mod_file.major_version == self.info.mod_file.comp_level
        ):
            log.debug("MODULE.bazel version matches release version; no patch needed.")
            return None  # No patch needed

        # Build metadata strings for logging
        file_meta = f"(version={self.info.mod_file.version}, comp_level={self.info.mod_file.comp_level})"
        release_meta = f"(version={self.info.release.version}, comp_level={self.info.mod_file.major_version})"
        log.info(
            f"MODULE.bazel {file_meta} doesn't match release {release_meta}; creating patch"
        )

        # Create patched content by replacing version
        stamped_content = re.sub(
            r"(version\s*=\s*['\"])([^'\"]+)(['\"])",
            lambda m: f"{m.group(1)}{self.info.release.version}{m.group(3)}",
            self.info.mod_file.content,
            count=1,
        )

        if self.info.release.version.semver:
            major_version = self.info.release.version.semver.major

            # Replace compatibility_level with major version
            stamped_content = re.sub(
                r"(compatibility_level\s*=\s*)(\d+)",
                lambda m: f"{m.group(1)}{major_version}",
                stamped_content,
                count=1,
            )

        # Generate unified diff patch
        patch_text = "".join(
            difflib.unified_diff(
                self.info.mod_file.content.splitlines(keepends=True),
                stamped_content.splitlines(keepends=True),
                fromfile="a/MODULE.bazel",
                tofile="b/MODULE.bazel",
                lineterm="\n",
            )
        )

        self.patches["module_dot_bazel_version.patch"] = patch_text

        # Bazel registry must contain the patched content
        return stamped_content

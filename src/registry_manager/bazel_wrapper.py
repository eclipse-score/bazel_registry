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
import tarfile
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import IO

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
            f"{metadata_path} has invalid versions field; expected list of semantic version strings"
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
            if not metadata_path.parent.is_dir():
                log.fatal(f"Module '{module_name}' does not exist in registry.")

            if m := try_parse_metadata_json(metadata_path):
                if not m.obsolete:
                    modules.append(m)
            else:
                log.fatal(f"Module '{module_name}' could not be found or parsed.")
    else:
        for module_dir in sorted(Path("modules").iterdir(), key=lambda p: p.name):
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
            f"{metadata_json} has invalid repository field; expected one element"
        )
        return None

    repo = data["repository"][0]
    if not isinstance(repo, str) or not repo.startswith("github:"):
        log.warning(f"{metadata_json} has non-GitHub repository '{repo}'; skipping")
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


def parse_MODULE_file_content(content: str) -> ModuleFileContent:  # noqa: N802
    """Parse the content of a MODULE.bazel file."""

    # This searches for the 'FIRST' module it can find
    raw_content = content
    module_match = re.search(r"module\s*\((.*?)\)", content, re.DOTALL)

    if not module_match:
        raise ValueError("No 'module' declaration found in MODULE.bazel")

    module_content = module_match.group(1)

    comp_level = None
    if m_cl := re.search(r"compatibility_level\s*=\s*(\d+)", module_content):
        comp_level = int(m_cl.group(1))

    version = None
    if m_ver := re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", module_content):
        version = str(m_ver.group(1))

    # If version is missing we add a placeholder.
    # This will assist us in replacing / adding it later in patches.
    has_version = version is not None

    if not has_version:
        module_start = module_match.start()
        module_end = module_match.end()

        to_insert = ""
        # If it ends in command don't add another.
        if module_content.strip() and not module_content.strip().endswith(","):
            to_insert = ","
        # unsure if the amount of spaces here is okay or should be dynamic?
        if not has_version:
            to_insert += '\n    version = ""'
            to_insert += "\n"

        # replacing the entire module() block seemed easier than adding it
        new_module = "module(" + module_content.rstrip() + to_insert + ")"
        content = content[:module_start] + new_module + content[module_end:]

    return ModuleFileContent(
        raw_content=raw_content,
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


# Hosts GitHub uses to serve repository archives. A token may only ever be sent
# to these hosts (over HTTPS); anything else risks leaking the credential.
_GITHUB_ARCHIVE_HOSTS = frozenset(
    {"github.com", "codeload.github.com", "api.github.com"}
)


def _is_allowed_token_url(url: str) -> bool:
    """True if url is HTTPS on an allowlisted GitHub archive host."""
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in _GITHUB_ARCHIVE_HOSTS


class _TokenSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Drop the Authorization header on any redirect that leaves the allowlist.

    urllib forwards all request headers (including Authorization) to the redirect
    target, so without this a redirect to a non-GitHub host would disclose the
    token.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None and not _is_allowed_token_url(newurl):
            new_req.remove_header("Authorization")
        return new_req


def _build_archive_request(url: str, token: str | None) -> urllib.request.Request:
    """Build a Request for a GitHub archive URL.

    A token is required to download private-repository archives; GitHub hides
    them with a 404 rather than a 401 without one. The token is only attached
    to allowlisted HTTPS GitHub hosts to avoid leaking it on redirects.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "score-bazel-registry"})
    if token:
        if not _is_allowed_token_url(url):
            raise ValueError(
                "Refusing to send GitHub token: URL must use HTTPS and target "
                f"an allowlisted GitHub archive host: {url!r}"
            )
        req.add_header("Authorization", f"Bearer {token}")
    return req


class ArchiveDownloadResult(tuple[str, str]):
    """Result of downloading a GitHub source archive.

    Inherits from ``tuple[str, str]`` for backward compatibility with code
    and tests unpacking ``(integrity, top_level_dir)``. Also carries
    ``module_bazel_content`` if MODULE.bazel was found in the archive root.
    """

    integrity: str
    top_level_dir: str
    module_bazel_content: str | None

    def __new__(
        cls,
        integrity: str,
        top_level_dir: str,
        module_bazel_content: str | None = None,
    ) -> "ArchiveDownloadResult":
        instance = super().__new__(cls, (integrity, top_level_dir))
        instance.integrity = integrity
        instance.top_level_dir = top_level_dir
        instance.module_bazel_content = module_bazel_content
        return instance


def download_github_archive(
    url: str, token: str | None = None
) -> ArchiveDownloadResult:
    """Download a GitHub source archive.

    Returns an ``ArchiveDownloadResult`` (which unpacks as ``(integrity, top_level_dir)``
    for compatibility) containing the ``sha256-<base64>`` hash of the bytes,
    the archive's top-level directory name, and optional ``MODULE.bazel`` content.
    """
    # GitHub names a tarball's top-level directory ``{owner}-{repo}-{sha}``, but
    # the SHA length depends on repository visibility — 7 characters for public
    # repos and the full 40 characters for private ones — so it cannot be
    # predicted from the API response. Reading it from the downloaded archive is
    # the only reliable way to set ``strip_prefix``.

    req = _build_archive_request(url, token)
    opener = urllib.request.build_opener(_TokenSafeRedirectHandler)

    h = hashlib.sha256()
    with opener.open(req, timeout=10) as resp, tempfile.TemporaryFile() as tmp:
        while chunk := resp.read(1024 * 1024):
            tmp.write(chunk)
            h.update(chunk)
        integrity = "sha256-" + base64.b64encode(h.digest()).decode("ascii")
        tmp.seek(0)
        top_level_dir = _archive_top_level_dir(tmp)
        tmp.seek(0)
        module_bazel_content = _extract_archive_module_bazel(tmp, top_level_dir)
    return ArchiveDownloadResult(integrity, top_level_dir, module_bazel_content)


def _archive_top_level_dir(archive: IO[bytes]) -> str:
    """Return the single top-level directory name inside a tar.gz archive.

    Raises ``ValueError`` if the archive does not contain exactly one top-level
    directory, which would be unexpected for a GitHub source archive.
    """
    # A valid GitHub source archive has a single top-level directory (e.g.
    # ``{owner}-{repo}-{sha}``) with all entries nested below it. An archive
    # that instead contains a bare top-level file (e.g. ``README``) must be
    # rejected, otherwise that filename would be returned as ``strip_prefix``
    # and produce unusable ``source.json`` metadata.
    with tarfile.open(fileobj=archive, mode="r:*") as tar:
        top_dirs: set[str] = set()
        top_files: set[str] = set()
        for member in tar.getmembers():
            # Tar archives can store member paths with leading './' (e.g., './dir/file')
            # or absolute slashes ('/dir/file') depending on how tar or git-archive was invoked.
            # Normalizing member names by stripping these prefixes ensures that partition('/')
            # correctly identifies the root directory rather than treating '.' or '' as a top-level folder.
            name = member.name.removeprefix("./").lstrip("/")
            if not name or name == ".":
                continue

            first, sep, _ = name.partition("/")

            # Skip POSIX tar (pax) and git-archive extended metadata headers.
            # When archiving files with long paths (>100 chars), high-precision timestamps,
            # or git metadata, git-archive generates a global header ('pax_global_header')
            # and extended header directories ('PaxHeaders.<PID>/...' or 'PaxHeaders/...').
            # These are tar format metadata, not actual project files/folders. If not skipped,
            # they would be counted as extra top-level files or directories and cause validation errors.
            if member.name == "pax_global_header" or first.startswith("PaxHeaders."):
                continue

            if sep:
                # Nested entry: lives under a top-level directory.
                top_dirs.add(first)
            elif member.isdir():
                # Explicit top-level directory entry.
                top_dirs.add(first)
            else:
                # Bare top-level file with no containing directory.
                top_files.add(first)
    if top_files or len(top_dirs) != 1:
        raise ValueError(
            "expected exactly one top-level directory in archive, got "
            f"directories={sorted(top_dirs)}, files={sorted(top_files)}"
        )
    return top_dirs.pop()


def _extract_archive_module_bazel(archive: IO[bytes], top_level_dir: str) -> str | None:
    """Extract the content of MODULE.bazel directly from the archive if present.

    Looks for '<top_level_dir>/MODULE.bazel' inside the archive.
    """
    with tarfile.open(fileobj=archive, mode="r:*") as tar:
        for member in tar.getmembers():
            name = member.name.removeprefix("./").lstrip("/")
            if not member.isfile():
                continue
            if name == f"{top_level_dir}/MODULE.bazel":
                f = tar.extractfile(member)
                if f is not None:
                    try:
                        return f.read().decode("utf-8")
                    except UnicodeDecodeError:
                        log.warning(
                            f"MODULE.bazel in {top_level_dir} could not be decoded as UTF-8"
                        )
                        return None
    return None


def sha256_from_string(content: str) -> str:
    """Compute SHA256 hash from a string."""
    return _sha256_from_bytes([content.encode("utf-8")])


class ModuleUpdateRunner:
    """Generates registry files for a module update.

    Creates or updates metadata.json, MODULE.bazel, patches/, and source.json
    for a module version.
    """

    def __init__(self, task_info: ModuleUpdateInfo, token: str | None = None):
        self.info = task_info
        self.token = token
        self.patches: dict[str, str] = {}
        self.module_path = Path("modules") / task_info.module.name
        self.module_version_path = self.module_path / str(task_info.release.version)

    @property
    def _download_url(self) -> str:
        """Returns the preferred download URL for the release archive.

        Prefers a stable release asset URL over the dynamic tarball URL.
        """
        return self.info.release.asset_url or self.info.release.tarball

    def generate_files(self, source_only: bool = False) -> None:
        """Generate all necessary registry files for this module update.

        Writes/updates:
        - metadata.json with the new version (skipped if source_only)
        - <version>/MODULE.bazel with patched content if needed (skipped if source_only)
        - patches/ directory with any necessary patches (skipped if source_only)
        - source.json with integrity hash and patch metadata
        """
        # 1. Download archive and extract integrity, archive root, and MODULE.bazel
        archive_info = download_github_archive(self._download_url, self.token)
        integrity = archive_info[0]
        archive_root = archive_info[1]
        archive_mod_content = getattr(archive_info, "module_bazel_content", None)

        is_source_only = (
            source_only
            or self.info.source_only
            or (self.info.mod_file is None and archive_mod_content is None)
        )
        source_json_path = self.module_version_path / "source.json"

        if is_source_only and not source_json_path.exists():
            log.fatal(
                f"Cannot perform source-only migration: {source_json_path} does not exist."
            )

        if not is_source_only:
            self._add_version_to_metadata()

            # Auto-detect whether the archive already has the module version set.
            # If MODULE.bazel was found in the archive, use it as the source of truth;
            # this prevents generating unnecessary or conflicting patches when release
            # assets already have the version stamped.
            if archive_mod_content:
                self.info.mod_file = parse_MODULE_file_content(archive_mod_content)

            patched_module_file = self._create_patch_for_module_version_if_mismatch()
            self._write_files(patched_module_file)

        self._generate_source_json(integrity=integrity, archive_root=archive_root)

    def _generate_source_json(
        self, integrity: str | None = None, archive_root: str | None = None
    ) -> None:
        """Generate or update source.json with integrity hash, strip_prefix, and patches."""
        if integrity is None or archive_root is None:
            archive_info = download_github_archive(self._download_url, self.token)
            integrity = archive_info[0]
            archive_root = archive_info[1]

        source_json_path = self.module_version_path / "source.json"
        patches_map: dict[str, str] = {}
        patch_strip = 1
        strip_prefix = archive_root

        # Read existing source.json if present to preserve patches and monorepo subdir prefix
        if source_json_path.exists():
            try:
                with open(source_json_path) as f:
                    old_source = json.load(f)
                if isinstance(old_source.get("patches"), dict):
                    patches_map.update(old_source["patches"])
                if "patch_strip" in old_source:
                    patch_strip = old_source["patch_strip"]
                if old_strip_prefix := old_source.get("strip_prefix"):
                    _old_root, _sep, module_subdir = old_strip_prefix.partition("/")
                    if module_subdir:
                        strip_prefix = f"{archive_root}/{module_subdir}"
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Could not read existing {source_json_path}: {e}")

        # Add any new patches generated in this run, overwriting any existing
        # patches with the same name.
        if self.patches:
            new_patches = {
                patch_name: sha256_from_string(patch_text)
                for patch_name, patch_text in self.patches.items()
            }
            patches_map.update(new_patches)

        source_dict: dict[str, object] = {
            "integrity": integrity,
            "strip_prefix": strip_prefix,
            "url": self._download_url,
            "archive_type": "tar.gz",
        }
        if patches_map:
            source_dict["patch_strip"] = patch_strip
            source_dict["patches"] = patches_map

        self.module_version_path.mkdir(parents=True, exist_ok=True)
        with open(source_json_path, "w") as f:
            json.dump(source_dict, f, indent=4)
            f.write("\n")

    def _add_version_to_metadata(self) -> None:
        """Add the new version to metadata.json and keep versions sorted."""
        metadata_path = self.module_path / "metadata.json"
        with open(metadata_path, "r+") as f:
            metadata = json.load(f)
            versions = _parse_versions(metadata.get("versions", []), metadata_path)

            if self.info.release.version in versions:
                log.debug(
                    f"Version {self.info.release.version} already present in metadata"
                    f" for module {self.info.module.name}; skipping metadata update."
                )
                return

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
        if self.info.mod_file is None:
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

        If the downloaded MODULE.bazel declares a different version than the
        release, a patch is created to stamp the correct version.

        Note: this is based on rather fragile regex replacements and may need
        adjustments for more complex MODULE.bazel files.
        Example that would fail:
        # module(this_is_just_a_comment, version='1.0.0')
        module(real_module)
        """
        if self.info.mod_file is None:
            raise ValueError("Module file content not available")

        file_version = self.info.mod_file.version
        version_was_missing = file_version is None

        # Check if no patch is needed
        if not version_was_missing and file_version == self.info.release.version:
            log.debug("MODULE.bazel version matches release version; no patch needed.")
            return None  # No patch needed

        effective_file_version = file_version or Version("0.0.0")

        # Build metadata strings for logging
        file_meta = f"(version={effective_file_version})"
        release_meta = f"(version={self.info.release.version})"
        log.debug(
            f"MODULE.bazel {file_meta} doesn't match release {release_meta}; creating patch"
        )

        # Create patched content by replacing version
        stamped_content = re.sub(
            # (version\s*=\s*['\"])([^'\"]*)(['\"])
            r"(version\s*=\s*['\"])([^'\"]*)(['\"])",
            lambda m: f"{m.group(1)}{self.info.release.version}{m.group(3)}",
            self.info.mod_file.content,
            count=1,
        )

        # Generate Patch difference
        patch_text = "".join(
            difflib.unified_diff(
                a=self.info.mod_file.raw_content.splitlines(True),
                b=stamped_content.splitlines(keepends=True),
                fromfile="a/MODULE.bazel",
                tofile="b/MODULE.bazel",
                lineterm="\n",
            )
        )

        self.patches["module_dot_bazel_version.patch"] = patch_text

        # Bazel registry must contain the patched content
        return stamped_content

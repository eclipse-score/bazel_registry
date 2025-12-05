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

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from registry_manager import gh_logging

log = gh_logging.MyLog()


@dataclass
class ModuleInfo:
    path: Path
    name: str
    org_and_repo: str
    versions: list[str]
    periodic_pull: bool
    obsolete: bool

    @property
    def latest_version(self) -> str | None:
        if not self.versions:
            return None
        return self.versions[-1]


def read_modules(module_names: list[str] | None) -> list[ModuleInfo]:
    """Read specific modules by name."""
    modules: list[ModuleInfo] = []
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


def try_parse_metadata_json(metadata_json: Path) -> ModuleInfo | None:
    module_path = metadata_json.parent
    if not module_path.is_dir():
        return None

    if not metadata_json.exists():
        log.warning(f"{metadata_json} does not exist; skipping")
        return None

    if not module_path.name.startswith("score_"):
        log.warning(f"{module_path} is not prefixed with 'score_'", file=metadata_json)

    with open(metadata_json) as f:
        data = json.load(f)

    if len(data["repository"]) != 1:
        log.warning(
            f"{metadata_json} has invalid repository field;"
            " Expected one element. skipping",
            file=metadata_json,
        )
        return None

    repo = data["repository"][0]
    if not repo.startswith("github:"):
        log.warning(
            f"{metadata_json} has non-GitHub repository '{repo}'; skipping",
            file=metadata_json,
        )
        return None

    return ModuleInfo(
        path=metadata_json.parent,
        name=metadata_json.parent.name,
        org_and_repo=repo[len("github:") :],
        versions=data.get("versions", []),
        periodic_pull=data.get("periodic-pull", False),
        obsolete=data.get("obsolete", False),
    )


@dataclass
class ModuleFileContent:
    content: str
    compatibility_level: int | None = None
    compatibility_level_line: int | None = None
    version: str | None = None
    version_line: int | None = None
    major_version: int | None = None


def parse_MODULE_file_content(content: str) -> ModuleFileContent:
    """Parse the content of a MODULE.bazel file."""

    compatibility_level = None
    version = None

    m_cl = re.search(r"compatibility_level\s*=\s*(\d+)", content)
    if m_cl:
        compatibility_level = int(m_cl.group(1))
        compatibility_level_line = content[: m_cl.start()].count("\n") + 1
    else:
        compatibility_level_line = None

    m_ver = re.search(r'version\s*=\s*"([^"]+)"', content)
    if m_ver:
        version = m_ver.group(1)
        version_line = content[: m_ver.start()].count("\n") + 1
    else:
        version_line = None

    return ModuleFileContent(
        content=content,
        compatibility_level=compatibility_level,
        compatibility_level_line=compatibility_level_line,
        version=version,
        version_line=version_line,
        major_version=int(version.split(".")[0]) if version else None,
    )


def _generate_source_json(
    new_version_dir: Path, tarball: str, org_and_repo: str, module_version: str
):
    source_dict = {}
    process = subprocess.run(
        f"curl -Ls {tarball}"
        + " | sha256sum | awk '{ print $1 }' | xxd -r -p | base64",
        capture_output=True,
        shell=True,
        text=True,
    )
    integrity = "sha256-" + process.stdout.strip()
    source_dict["integrity"] = str(integrity)
    source_dict["strip_prefix"] = f"{org_and_repo.split('/')[-1]}-{module_version}"
    source_dict["url"] = tarball
    with open(new_version_dir / "source.json", "w") as f:
        print(json.dumps(source_dict, indent=4), file=f)


def _add_version_to_metadata(module: ModuleInfo, new_version: str):
    metadata_path = Path("modules") / module.name / "metadata.json"

    with metadata_path.open("r+") as f:
        metadata = json.load(f)
        assert new_version not in metadata["versions"]
        metadata["versions"].append(new_version)
        metadata["versions"] = sorted(metadata["versions"], reverse=True)
        f.seek(0)
        print(json.dumps(metadata, indent=4), file=f)


def add_version(
    module: ModuleInfo,
    new_version: str,
    bazel_module_file_content: str,
    tarball: str,
):
    module_path = Path("modules") / module.name
    _add_version_to_metadata(module, new_version)
    new_version_dir = module_path / new_version
    new_version_dir.mkdir(exist_ok=True)
    with open(new_version_dir / "MODULE.bazel", "w") as f:
        f.write(bazel_module_file_content)
    _generate_source_json(new_version_dir, tarball, module.org_and_repo, new_version)

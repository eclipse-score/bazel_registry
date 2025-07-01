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
import subprocess
from pathlib import Path

import requests


def generate_source_json(new_version_dir: Path, tarball: str, repo_name: str, module_version: str): 
    source_dict = {}
    process = subprocess.run(f"curl -Ls {tarball}" + " | sha256sum | awk '{ print $1 }' | xxd -r -p | base64", capture_output=True, shell=True, text=True)
    integrity = "sha256-" + process.stdout.strip()
    source_dict["integrity"] = str(integrity)
    source_dict["strip_prefix"] = f"{repo_name}-{module_version}"
    source_dict["url"] = tarball
    with open(new_version_dir / "source.json", "w") as f:
        f.write(json.dumps(source_dict, indent=4))

def change_metadata(module_path: Path, module_name: str, module_version: str): 
    metadata_path = module_path / "metadata.json"

    with metadata_path.open("r") as f:
        metadata = json.load(f)
    if module_version not in metadata["versions"]:
        metadata["versions"].append(module_version)
    with metadata_path.open("w") as f:
        json.dump(metadata, f, indent=4)

def generate_needed_files(module_name: str, module_version: str, bazel_module_file_content: str, tarball: str, repo_name: str):
    module_path = Path("modules") / module_name
    change_metadata(module_path, module_name, module_version) 
    new_version_dir = module_path / module_version
    new_version_dir.mkdir(exist_ok=True)
    with open(new_version_dir / "MODULE.bazel", "w") as f:
       f.write(bazel_module_file_content)
    generate_source_json(new_version_dir, tarball,repo_name, module_version)



if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description='Download GitHub release files')
    parser.add_argument("--repo_name", help="Name of the repository")
    parser.add_argument('--module_file_url', help='Repository in format owner/repo')
    parser.add_argument('--module_name', help='Name of the folder of the to be release module (in bazel_registry)')
    parser.add_argument('--module_version', help='Module version')
    parser.add_argument('--tarball', help='Download source tarball')

    # 1. get the module.bazel file
    args = parser.parse_args()
    bazel_file_url = args.module_file_url.replace("https://github.com","https://raw.githubusercontent.com").replace("blob", "refs/tags")
    r = requests.get(bazel_file_url)
    assert r.ok
    module_text = r.text
    generate_needed_files(args.module_name, args.module_version, module_text, args.tarball, args.repo_name)

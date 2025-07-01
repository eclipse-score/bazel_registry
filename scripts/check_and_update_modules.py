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
import os
from urllib.parse import urlparse

import requests
from generate_module_files import generate_needed_files
from github import Github


def get_actual_versions_from_metadata(modules_path="modules"):
    actual_modules_versions = {}
    for module_name in os.listdir(modules_path):
        module_dir = os.path.join(modules_path, module_name)
        metadata_path = os.path.join(module_dir, "metadata.json")
        if os.path.isdir(module_dir) and os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    versions = metadata.get("versions", [])
                    if versions:
                        actual_modules_versions[module_name] = versions[-1]
                    else:
                        actual_modules_versions[module_name] = None
            except Exception as e:
                print(f"Error reading {metadata_path}: {e}")
                actual_modules_versions[module_name] = None
    return actual_modules_versions

def get_latest_release_info(repo_url: str, github_token: str = ""):
    try:
        path_parts = urlparse(repo_url).path.strip('/').split('/')
        if len(path_parts) != 2:
            raise ValueError("Invalid GitHub repo URL format")
        owner, repo_name = path_parts

        gh = Github(github_token) if github_token else Github()
        repo = gh.get_repo(f"{owner}/{repo_name}")

        release = repo.get_latest_release()
        version = release.tag_name
        tarball = release.tarball_url

        return repo_name, version, tarball

    except Exception as e:
        print(f"Error fetching release info for {repo_url}: {e}")
        return None, None, None

def enrich_modules(modules_list, actual_versions_dict, github_token=""):
    enriched = []
    for module in modules_list:
        module_name = module["module_name"]
        module_url = module["module_url"]

        repo_name, version, tarball = get_latest_release_info(module_url, github_token)
        if version is None:
            print(f"Skipping module {module_name} due to missing release info.")
            continue

        clean_version = version.lstrip("v")
        actual_version = actual_versions_dict.get(module_name)

        if clean_version != actual_version:
            enriched.append({
                "module_name": module_name,
                "module_url": module_url,
                "repo_name": repo_name,
                "module_version": clean_version,
                "tarball": tarball,
                "module_file_url": f"{module_url}/blob/{version}/MODULE.bazel"
            })
        else:
            print(f"Module {module_name} is up to date (version {clean_version})")

    return enriched

def process_module(module):
    bazel_file_url = module["module_file_url"].replace("https://github.com", "https://raw.githubusercontent.com").replace("blob", "refs/tags")
    r = requests.get(bazel_file_url)
    if not r.ok:
        print(f"Failed to fetch MODULE.bazel for {module['module_name']}")
        return

    bazel_content = r.text
    generate_needed_files(
        module_name=module["module_name"],
        module_version=module["module_version"],
        bazel_module_file_content=bazel_content,
        tarball=module["tarball"],
        repo_name=module["repo_name"]
    )
    print(f"✅ Successfully processed {module['module_name']}")

if __name__ == "__main__":
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

    modules = [
        {
            "module_name": "score_docs_as_code",
            "module_url": "https://github.com/eclipse-score/docs-as-code",
        },
        {
            "module_name": "score_process",
            "module_url": "https://github.com/eclipse-score/process_description",
        },
        {
            "module_name": "score_platform",
            "module_url": "https://github.com/eclipse-score/score",
        },
        {
            "module_name": "score_toolchains_gcc",
            "module_url": "https://github.com/eclipse-score/toolchains_gcc",
        },
    ]

    actual_versions = get_actual_versions_from_metadata("modules")
    modules_to_update = enrich_modules(modules, actual_versions, GITHUB_TOKEN)

    if not modules_to_update:
        print("No modules need update.")
        print("[]")
    else:
        module_list = "\n".join(
            [f"- **{m['module_name']}**: {actual_versions.get(m['module_name'], 'unknown')} ➜ {m['module_version']}" for m in modules_to_update]
        )
        print("### Modules needing update (markdown list):")
        print(module_list)

        for module in modules_to_update:
            process_module(module)

        print(json.dumps(modules_to_update))

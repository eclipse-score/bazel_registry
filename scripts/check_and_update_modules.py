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
import re
from urllib.parse import urlparse

import requests
from generate_module_files import generate_needed_files
from github import Github


def extract_module_version(bazel_content: str) -> str:
    match = re.search(r'version\s*=\s*"([^"]+)"', bazel_content)
    if match:
        return match.group(1)
    return ""

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
                    actual_modules_versions[module_name] = versions[-1] if versions else None
            except Exception as e:
                print(f"Error reading {metadata_path}: {e}")
                actual_modules_versions[module_name] = None
    return actual_modules_versions

def get_all_releases(repo_url: str, github_token: str = ""):
    """
    Fetch all releases (including pre-releases) from a GitHub repo.
    Returns sorted list of dicts with version info.
    """
    try:
        path_parts = urlparse(repo_url).path.strip('/').split('/')
        if len(path_parts) != 2:
            raise ValueError("Invalid GitHub repo URL format")
        owner, repo_name = path_parts

        gh = Github(github_token) if github_token else Github()
        repo = gh.get_repo(f"{owner}/{repo_name}")

        all_releases = []
        for release in repo.get_releases():
            all_releases.append({
                "version": release.tag_name.lstrip("v"),
                "tag_name": release.tag_name,
                "tarball": f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{release.tag_name}.tar.gz",
                "published_at": release.published_at,
                "prerelease": release.prerelease,
            })

        # Return oldest to newest for queue processing
        return sorted(all_releases, key=lambda r: r["published_at"])

    except Exception as e:
        print(f"Error fetching releases for {repo_url}: {e}")
        return []

def enrich_modules(modules_list, actual_versions_dict, github_token="", max_releases=5):
    """
    Builds list of modules to be enriched by checking the latest (or oldest N) unprocessed releases.
    """
    enriched = []

    for module in modules_list:
        module_name = module["module_name"]
        module_url = module["module_url"]
        current_version = actual_versions_dict.get(module_name)

        releases = get_all_releases(module_url, github_token)

        # Process only the N oldest releases that are not yet added
        count = 0
        for release in releases:
            if release["version"] == current_version:
                break  # Stop when we hit the current live version

            # Validate pre-release has suffix
            if release["prerelease"]:
                if not re.search(r"\d+\.\d+\.\d+-[A-Za-z]+", release["tag_name"]):
                    print(
                        f"Skipping pre-release '{release['tag_name']}' for {module_name}: "
                        "Pre-release version must include a suffix (e.g., -alpha, -rc)."
                    )
                    continue

            enriched.append({
                "module_name": module_name,
                "module_url": module_url,
                "repo_name": module_url.split("/")[-1],
                "module_version": release["version"],
                "tarball": release["tarball"],
                "module_file_url": f"{module_url}/blob/{release['tag_name']}/MODULE.bazel"
            })

            count += 1
            if count >= max_releases:
                break

    return enriched

def process_module(module):
    bazel_file_url = module["module_file_url"].replace("https://github.com", "https://raw.githubusercontent.com").replace("blob", "refs/tags")
    r = requests.get(bazel_file_url)
    if not r.ok:
        print(f"Failed to fetch MODULE.bazel for {module['module_name']}@{module['module_version']}")
        return

    bazel_content = r.text
    declared_version = extract_module_version(bazel_content)

    if declared_version != module["module_version"]:
        print(
            f"Skipping {module['module_name']}@{module['module_version']}: "
            f"Version mismatch (expected {module['module_version']}, declared {declared_version})"        )
        return

    generate_needed_files(
        module_name=module["module_name"],
        module_version=module["module_version"],
        bazel_module_file_content=bazel_content,
        tarball=module["tarball"],
        repo_name=module["repo_name"]
    )
    print(f"Successfully processed {module['module_name']}@{module['module_version']}")

def load_modules_from_json(json_path="scripts/modules.json"):
    try:
        with open(json_path, "r") as f:
            modules = json.load(f)
            return modules
    except Exception as e:
        print(f"Error reading modules JSON file: {e}")
        return []
    
if __name__ == "__main__":
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

    modules = load_modules_from_json()

    actual_versions = get_actual_versions_from_metadata("modules")
    modules_to_update = enrich_modules(modules, actual_versions, GITHUB_TOKEN)

    if not modules_to_update:
        print("No modules need update.\n[]")
    else:
        module_list = "\n".join([
            f"- **{m['module_name']}** ➜ {m['module_version']}" for m in modules_to_update
        ])
        print("### Modules queued for update (in PR):")
        print(module_list)

        for module in modules_to_update:
            process_module(module)

        print(json.dumps(modules_to_update, indent=2))
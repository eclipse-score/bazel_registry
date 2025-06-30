import json
import os
import subprocess
from urllib.parse import urlparse

from github import Github


def get_actual_versions(modules_path="modules"):
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

        try:
            release = repo.get_latest_release()
            version = release.tag_name
            tarball = release.tarball_url
        except:
            tags = repo.get_tags()
            if tags.totalCount == 0:
                raise Exception("No tags found")
            tag = tags[0]
            version = tag.name
            tarball = f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{version}.tar.gz"

        return version, tarball

    except Exception as e:
        print(f"Error fetching release info for {repo_url}: {e}")
        return None, None


def enrich_modules(modules_list, actual_versions_dict, github_token=""):
    enriched = []
    for module in modules_list:
        module_name = module["module_name"]
        module_url = module["module_url"]
        repo_name = module["repo_name"]

        version, tarball = get_latest_release_info(module_url, github_token)
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


def call_helper_script(module):
    """
    Calls helper.py with the appropriate arguments for each outdated module.
    """
    cmd = [
        "python3",
        "scripts/generate_module_files.py",
        "--repo_name", module["repo_name"],
        "--module_file_url", module["module_file_url"],
        "--module_name", module["module_name"],
        "--module_version", module["module_version"],
        "--tarball", module["tarball"],
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"⚠️ Error running helper.py for {module['module_name']}")
    else:
        print(f"✅ Successfully processed {module['module_name']}")


if __name__ == "__main__":
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

    modules = [
        {
            "module_name": "score_docs_as_code",
            "module_url": "https://github.com/eclipse-score/docs-as-code",
            "repo_name": "docs-as-code",
        },
        {
            "module_name": "score_process",
            "module_url": "https://github.com/eclipse-score/process_description",
            "repo_name": "process_description",
        },
        {
            "module_name": "score_platform",
            "module_url": "https://github.com/eclipse-score/score",
            "repo_name": "score",
        },
        {
            "module_name": "score_toolchains_gcc",
            "module_url": "https://github.com/eclipse-score/toolchains_gcc",
            "repo_name": "toolchains_gcc",
        },
    ]

    actual_versions = get_actual_versions("modules")
    modules_to_update = enrich_modules(modules, actual_versions, GITHUB_TOKEN)

    if not modules_to_update:
        print("No modules need update.")
        # Print an empty JSON array so workflow step output is valid
        print("[]")
    else:
        # Create a markdown list string for PR body
        module_list = "\n".join(
            [f"- **{m['module_name']}**: {actual_versions.get(m['module_name'], 'unknown')} ➜ {m['module_version']}" for m in modules_to_update]
        )

        print("### Modules needing update (markdown list):")
        print(module_list)

        # Call helper script for each module
        for module in modules_to_update:
            call_helper_script(module)

        # Print raw JSON so workflow step can capture it as output
        print(json.dumps(modules_to_update))

# Score Bazel modules registry

## Usage
Add the following lines to your .bazelrc:
```
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build
```

## Development Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Development: repository structure
The repository is structured as follows:
- `modules/`: Contains the actual bazel modules in the registry.
- `src/`: Contains all the scripts to manage the registry.
- `tests/`: Contains the tests for the registry management scripts.
- `.github/`: Contains the GitHub workflows for automation.

## Release automation

The release automation workflow will run hourly and check for new releases of modules in the bazel registry.
If a new release is found, it will create a PR with the updated module information.

In case an urgent release of a module is needed, run the  ```check_new_releases``` workflow manually.

## How to compute the sha256 sum

```bash
curl -Ls https://github.com/eclipse-score/tooling/archive/refs/tags/release-0.5.0.tar.gz   | sha256sum   | awk '{ print $1 }'   | xxd -r -p   | base64   | sed 's/^/sha256-/'
```

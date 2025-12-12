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

# Run script via:
python -m src.registry_manager.main
```

## Development: repository structure
The repository is structured as follows:
* `modules/`: Contains the actual bazel modules in the registry.
* `src/`: Contains all the scripts to manage the registry.
* `tests/`: Contains the tests for the registry management scripts.
* `.github/`: Contains the GitHub workflows for automation.

## Release automation

The release automation workflow will run hourly and check for new releases of modules in the bazel registry.
If a new release is found, it will create a PR with the updated module information.

In case an urgent release of a module is needed, run the  `check_new_releases` workflow manually.

## Manual release of a module
To manually update a module which is not marked for automatic updates, run the following command, e.g., to update the `communication` module:

```bash
python -m src.registry_manager.main score_communication
```

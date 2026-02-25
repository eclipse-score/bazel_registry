# S-Core Bazel Registry

This repository hosts the S-Core Bazel module registry. It provides versioned
Bazel modules for use with Bzlmod and automates tracking of upstream module
releases.

The registry does not host module source code. It only contains metadata and
release information.


## Module Maintainers: Adding and Updating Modules

### Adding a New Module

To add a new module:

1. Create `modules/<module_name>/metadata.json`, using existing metadata files as reference. Set `periodic-pull: true` in the metadata file to enable automatic release tracking.
2. Open and merge a pull request
3. After merging, add the first release using the release process below


### Adding a New Release

Module releases are handled automatically if `periodic-pull: true` is set in the
module's metadata file.

A scheduled GitHub Actions workflow:
- runs every 30 minutes
- checks upstream GitHub releases
- opens a pull request when a new release is detected

If `periodic-pull: true` is NOT set, releases must be added manually:
trigger the "Check for Module Updates" workflow manually via GitHub Actions
and provide the module name as input.

### Urgent Releases

If a release is needed immediately, trigger the "Check for Module Updates"
workflow manually via GitHub Actions.


## Consumers: Using the Registry

Add the S-Core registry to your Bazel configuration. It is typically used
alongside the Bazel Central Registry (BCR).

Add the registry to your `.bazelrc`:
```
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build
```

## Registry Developers

This section is only relevant if you are working on the registry tooling.


### Development Environment

The registry tooling is implemented in Python.

Setup steps:
```bash
uv sync --dev

# Run script via:
uv run registry-manager
```

### Repository Structure

- `modules/` - Bazel module metadata and versioned module entries
- `src/` - Registry management scripts
- `tests/` - Test suite for the registry scripts
- `.github/` - GitHub Actions workflows and scheduled automation


## Questions and Contributions

Please use GitHub Issues and pull requests for questions, bug reports, and
improvements. You can also reach us via #score-infrastructure on the S-Core Slack.

Keep issues scoped to registry behavior, automation, and metadata correctness.
Module-specific issues should generally be reported upstream.

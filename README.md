# Score Bazel modules registry

## Usage
Add the following lines to your .bazelrc:
```
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build
```

## Development

```bash
# IDE setup
bazel run //tools:ide_support

# Verify licenses:
bazel run //tools:license.check.license_check

# Verify copyright:
bazel run //tools:copyright.check
```
## Release automation

The release automation workflow will run 2 times a day once in 12 AM and once in 12 PM.
In case the user need an urgent release of a module to be merged he can still run the file ```scripts/check_and_update_modules.py``` and it will do the work of checking the versions for you, he just need to push the PR by himself after the script is complete.
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

In case an urgent release of a module is needed, run the  ```check_new_releases``` workflow manually.
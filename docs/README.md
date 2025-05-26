# S-CORE Bazel Registry (SBR) contribution guidelines

TBD!

## How to compute the sha256 sum

```bash
curl -Ls https://github.com/eclipse-score/tooling/archive/refs/tags/release-0.5.0.tar.gz   | sha256sum   | awk '{ print $1 }'   | xxd -r -p   | base64   | sed 's/^/sha256-/'
```

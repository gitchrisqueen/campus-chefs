#!/usr/bin/env bash
# Renders every Mermaid diagram in README.md and docs/architecture.md with a pinned mermaid-cli
# image (plan phase 11 exit). Any diagram that fails to parse makes this script exit non-zero.
# The SVGs and the rewritten Markdown go to test-results/, which is git-ignored.
#
# Image checked on 2026-11-19 with `docker buildx imagetools inspect`: tag 12.0.1 was created on
# 2026-11-02, so it is more than 14 days old (docs/architecture.md records the details).
#
# Usage: scripts/render-mermaid.sh [FILE.md ...]   (or `make docs-check`)
set -euo pipefail

MERMAID_IMAGE="minlag/mermaid-cli:12.0.1@sha256:18938e53497376d524e04b1fc0bf7b6d61a491ce9ff7032bb2855d57155acb10"

cd "$(dirname "$0")/.."
[ "$#" -gt 0 ] || set -- README.md docs/architecture.md
mkdir -p test-results

for f in "$@"; do
  if ! grep -q '^```mermaid' "${f}"; then
    echo "render-mermaid: ${f} has no mermaid block" >&2
    exit 1
  fi
  docker run --rm -u "$(id -u):$(id -g)" -v "${PWD}:/data" "${MERMAID_IMAGE}" \
    -p /data/docs/puppeteer.json -i "/data/${f}" -o "/data/test-results/$(basename "${f}")"
done
echo "render-mermaid: $# file(s) rendered"

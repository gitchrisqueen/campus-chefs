#!/usr/bin/env bash
# Renders the 2008 landing page (legacy/view/welcome.php) to static HTML.
#
# STATIC RENDERING ONLY. The 2008 app is never run as a service: no web server,
# no database connection, and no other legacy page is executed. The one page
# rendered here (welcome.php) needs no database. PHP runs once as a CLI process,
# its stdout becomes welcome.html, and the container exits. The container has no
# network, a read-only root filesystem, and a read-only mount of the scratch copy.
#
# Output: test-results/legacy-render/view/welcome.html (git-ignored). The
# `tests` compose service can read it, because it bind-mounts test-results/.
# scripts/capture_screenshots.py --before screenshots it through file://, so the
# relative ../css and ../img paths resolve inside the scratch copy.
#
# Usage: legacy-support/render-static.sh   (run from anywhere)
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${repo}/test-results/legacy-render"

# Pinned by index digest. Tag php:8.5.11-cli-trixie was pushed 2026-10-21 (28 days
# before the digest was resolved). Digest resolved 2026-11-18 with
# `docker buildx imagetools inspect php:8.5.11-cli-trixie`. Re-resolve it the same
# way, and pick a release at least 14 days old, when you bump it.
PHP_IMAGE="php:8.5.11-cli-trixie@sha256:8e5d746f87655d89573e76d2b9125ed1b1578e47d3c466a2b2fdfc35593d9b41"

# Fresh scratch copy every run. legacy/ itself is never written to.
rm -rf "${out}"
mkdir -p "${out}"
cp -R "${repo}/legacy/." "${out}/"
# Let the tests container (uid 10001) read everything.
chmod -R a+rX "${out}"

# The scratch copy is mounted read-only, so PHP cannot change it. The HTML comes
# back on stdout and the host shell writes it. PHP warnings go to stderr, which
# is kept in render.log (PHP 8 warns about code written for PHP 5).
docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --user 10001:10001 \
  --pids-limit 64 \
  --memory 128m \
  -v "${out}:/work:ro" \
  -w /work/view \
  "${PHP_IMAGE}" \
  php -d display_errors=0 welcome.php \
  > "${out}/view/welcome.html" 2> "${out}/../legacy-render.log"

# The rendered file is the only thing the screenshot step needs.
test -s "${out}/view/welcome.html"
echo "render-static: wrote ${out#"${repo}"/}/view/welcome.html"

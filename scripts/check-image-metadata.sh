#!/usr/bin/env bash
# Fails if any image under the given paths carries EXIF, XMP, IPTC, GPS,
# Photoshop or comment metadata (plan 5.6). Prints file and tag names only,
# never tag values. Needs exiftool and jq.
#
# Usage: scripts/check-image-metadata.sh DIR_OR_FILE...
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 DIR_OR_FILE..." >&2
  exit 2
fi
for tool in exiftool jq; do
  command -v "${tool}" >/dev/null || { echo "check-image-metadata: ${tool} not found" >&2; exit 2; }
done

json="$(exiftool -j -q -q -m -r -G1 \
  -ext jpg -ext jpeg -ext png -ext gif -ext webp \
  -EXIF:all -XMP:all -IPTC:all -GPS:all -Photoshop:all -Comment \
  "$@" || true)"

if [ -z "${json}" ]; then
  echo "check-image-metadata: no images found under $*" >&2
  exit 2
fi

filter='.[] | select((keys | length) > 1)
  | "\(.SourceFile): \([keys[] | select(. != "SourceFile")] | join(", "))"'
bad="$(printf '%s' "${json}" | jq -r "${filter}")"
total="$(printf '%s' "${json}" | jq 'length')"

if [ -n "${bad}" ]; then
  printf '%s\n' "${bad}"
  echo "check-image-metadata: $(printf '%s\n' "${bad}" | wc -l | tr -d ' ') of ${total} image(s) carry metadata"
  exit 1
fi
echo "check-image-metadata: ${total} image(s) clean"

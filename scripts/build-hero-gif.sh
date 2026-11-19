#!/usr/bin/env bash
# Builds the README's animated hero, docs/screenshots/after/hero.gif, from the first eight
# walkthrough pictures (docs/screenshots/walkthrough/01-*.png to 08-*.png, the E2E-01 story).
# `scripts/capture_screenshots.py --walkthrough` writes those pictures.
#
# Each frame is an unedited screenshot of the running demo. ffmpeg only joins them: one shared
# palette, no dithering, no audio, no metadata. The container has no network and sees two folders.
#
# Image checked on 2026-11-19 with `docker buildx imagetools inspect`: the 9.0.2-1 image was
# created on 2026-10-09, so it is more than 14 days old.
#
# Usage: scripts/build-hero-gif.sh   (or `make screenshots`, which also captures the pictures)
set -euo pipefail

FFMPEG_IMAGE="mwader/static-ffmpeg:9.0.2-1@sha256:f5d100184884eb3e82b0eb14bb5ebf98da99826ac824989720297fb9ef21c822"
FRAMES="01 02 03 04 05 06 07 08"
HOLD_SECONDS=1.6        # every frame
LAST_HOLD_SECONDS=3.0   # the closing frame, before the loop restarts
MAX_BYTES=3000000

cd "$(dirname "$0")/.."
src="docs/screenshots/walkthrough"
out="docs/screenshots/after"
work="test-results/hero"

# ffmpeg's concat list: a duration per frame; the last frame is listed twice so its duration counts.
mkdir -p "${work}" "${out}"
list="${work}/frames.txt"
: > "${list}"
last=""
for n in ${FRAMES}; do
  f="$(cd "${src}" && ls -1 -- "${n}"-*.png 2>/dev/null | head -1 || true)"
  if [ -z "${f}" ]; then
    echo "build-hero-gif: no ${src}/${n}-*.png; run capture_screenshots.py --walkthrough first" >&2
    exit 2
  fi
  if [ -n "${last}" ]; then printf "file '/in/%s'\nduration %s\n" "${last}" "${HOLD_SECONDS}" >> "${list}"; fi
  last="${f}"
done
printf "file '/in/%s'\nduration %s\nfile '/in/%s'\n" "${last}" "${LAST_HOLD_SECONDS}" "${last}" >> "${list}"

docker run --rm --network none -u "$(id -u):$(id -g)" \
  -v "${PWD}/${src}:/in:ro" -v "${PWD}/${work}:/work:ro" -v "${PWD}/${out}:/out" \
  "${FFMPEG_IMAGE}" -hide_banner -loglevel error -y \
  -f concat -safe 0 -i /work/frames.txt \
  -filter_complex "[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=none" \
  -fps_mode vfr -an -map_metadata -1 -loop 0 /out/hero.gif

size="$(wc -c < "${out}/hero.gif" | tr -d ' ')"
if [ "${size}" -gt "${MAX_BYTES}" ]; then
  echo "build-hero-gif: ${out}/hero.gif is ${size} bytes, over the ${MAX_BYTES} byte limit" >&2
  exit 1
fi
echo "build-hero-gif: ${out}/hero.gif, $(echo "${FRAMES}" | wc -w | tr -d ' ') frames, ${size} bytes"

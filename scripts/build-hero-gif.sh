#!/usr/bin/env bash
# Builds two animations from the walkthrough pictures (docs/screenshots/walkthrough/NN-*.png, the
# E2E-01 story). `scripts/capture_screenshots.py --walkthrough` writes those pictures.
#
# - docs/screenshots/after/hero.gif: the README's embedded hero. Four screens, played once. It has
#   no loop extension, so it stops on its last frame, and all its frame delays add up to 4.7 seconds.
#   WCAG 2.2.2 allows motion that starts by itself only if it stops within 5 seconds, and
#   scripts/check_docs.py (`make lint`) fails on an embedded GIF that loops or runs longer.
# - docs/screenshots/after/booking-loop.gif: all eight screens in a loop of about 14 seconds. The
#   README only links to it, so it moves only for a reader who opens it.
#
# Each frame is a screenshot of the running demo. ffmpeg only joins them: one shared palette, no
# dithering, no audio, no metadata. The container has no network and sees two folders.
#
# Image checked on 2026-11-19 with `docker buildx imagetools inspect`: the 9.0.2-1 image was
# created on 2026-10-09, so it is more than 14 days old.
#
# Usage: scripts/build-hero-gif.sh   (or `make screenshots`, which also captures the pictures)
set -euo pipefail

FFMPEG_IMAGE="mwader/static-ffmpeg:9.0.2-1@sha256:f5d100184884eb3e82b0eb14bb5ebf98da99826ac824989720297fb9ef21c822"
MAX_BYTES=3000000

cd "$(dirname "$0")/.."
src="docs/screenshots/walkthrough"
out="docs/screenshots/after"
work="test-results/hero"
mkdir -p "${work}" "${out}"

# build NAME "FRAMES" HOLD_SECONDS LAST_HOLD_CENTISECONDS LOOP
# LOOP is ffmpeg's GIF option: 0 loops forever, -1 writes no loop extension (the GIF plays once).
build() {
  local name="$1" frames="$2" hold="$3" last_hold_cs="$4" loop="$5"
  local list="${work}/${name}.txt" n f size
  : > "${list}"
  for n in ${frames}; do
    f="$(cd "${src}" && ls -1 -- "${n}"-*.png 2>/dev/null | head -1 || true)"
    if [ -z "${f}" ]; then
      echo "build-hero-gif: no ${src}/${n}-*.png; run capture_screenshots.py --walkthrough first" >&2
      exit 2
    fi
    # ffmpeg's concat list: one duration per frame. The last frame's hold comes from -final_delay.
    printf "file '/in/%s'\nduration %s\n" "${f}" "${hold}" >> "${list}"
  done

  docker run --rm --network none -u "$(id -u):$(id -g)" \
    -v "${PWD}/${src}:/in:ro" -v "${PWD}/${work}:/work:ro" -v "${PWD}/${out}:/out" \
    "${FFMPEG_IMAGE}" -hide_banner -loglevel error -y \
    -f concat -safe 0 -i "/work/${name}.txt" \
    -filter_complex "[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=none" \
    -fps_mode vfr -an -map_metadata -1 -final_delay "${last_hold_cs}" -loop "${loop}" "/out/${name}.gif"

  size="$(wc -c < "${out}/${name}.gif" | tr -d ' ')"
  if [ "${size}" -gt "${MAX_BYTES}" ]; then
    echo "build-hero-gif: ${out}/${name}.gif is ${size} bytes, over the ${MAX_BYTES} byte limit" >&2
    exit 1
  fi
  echo "build-hero-gif: ${out}/${name}.gif, $(echo "${frames}" | wc -w | tr -d ' ') frames, ${size} bytes"
}

# The hero: search, the request form, "Request sent", then the diner's confirmed booking as the still.
# 3 x 1.4 s + 0.5 s = 4.7 s, then it stops.
build hero "02 04 05 08" 1.4 50 -1
# The full story: 7 x 1.6 s + 3.0 s = 14.2 s per pass, looping.
build booking-loop "01 02 03 04 05 06 07 08" 1.6 300 0

"""Docs checks for README.md and docs/*.md. Exit 1 if any check fails.

- Every relative link and image path points at a file or folder in the repository.
- Every `#anchor` matches a heading in the file it points at (GitHub's heading ids).
- Every image has alt text.
- Every `<source srcset>` inside a `<picture>` points at a file in the repository.
- Every animated image (`.gif`) sits inside a `<picture>` whose
  `<source media="(prefers-reduced-motion: reduce)">` offers a still picture.
- No embedded GIF (`<img src>`, `<source srcset>` or `![...](...)`) loops forever or moves for more
  than 5 seconds in total (WCAG 2.2.2). The GIF's own blocks are read: the frame delays and the
  NETSCAPE loop extension. A GIF that is only linked is exempt, because the reader starts it.
- The first Mermaid diagram in README.md and in docs/architecture.md names every service,
  network and volume that compose.yaml declares.

External (http, https, mailto) links are not fetched: this runs without network access.

Run: python scripts/check_docs.py   (part of `make lint`)
"""

import re
import struct
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
MD_LINK = re.compile(r"(!?)\[((?:[^\]\\]|\\.)*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_TAG = re.compile(r"<(img|a|source)\b([^>]*)>", re.I)
PICTURE = re.compile(r"<picture\b.*?</picture>", re.S | re.I)
GIF_IMAGE = re.compile(r"(?:\bsrc\s*=\s*\"|!\[[^\]]*\]\(\s*<?)([^\")\s>]+\.gif)\b", re.I)
REDUCED_MOTION = re.compile(r"prefers-reduced-motion\s*:\s*reduce", re.I)
ATTR = re.compile(r"([a-zA-Z-]+)\s*=\s*\"([^\"]*)\"")
MAX_MOTION_SECONDS = 5.0  # WCAG 2.2.2: motion that starts by itself must stop within 5 seconds
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def prose_lines(path: Path):
    """Yield (line number, text) for every line outside a fenced code block."""
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line.strip()):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


def slug(heading: str) -> str:
    """GitHub's heading id: lower case, punctuation dropped, each space becomes a hyphen."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)  # keep link text only
    text = re.sub(r"[`*_]", "", text).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    found: set[str] = set()
    for _, line in prose_lines(path):
        m = HEADING.match(line)
        if not m:
            continue
        base = slug(m.group(2))
        candidate, n = base, 0
        while candidate in found:  # GitHub numbers repeated headings: name, name-1, name-2
            n += 1
            candidate = f"{base}-{n}"
        found.add(candidate)
    return found


def srcset_paths(srcset: str) -> list[str]:
    """The URLs of a srcset value, without their width or density descriptors."""
    return [part.split()[0] for part in srcset.split(",") if part.strip()]


def offers_still(picture: str) -> bool:
    """True if a <source> for readers who ask for reduced motion points at pictures that do not move."""
    for tag, attrs in HTML_TAG.findall(picture):
        found = dict((k.lower(), v) for k, v in ATTR.findall(attrs))
        paths = srcset_paths(found.get("srcset", ""))
        if tag.lower() == "source" and REDUCED_MOTION.search(found.get("media", "")) and paths:
            if not any(p.lower().endswith(".gif") for p in paths):
                return True
    return False


def check_motion(path: Path, failures: list[str]) -> None:
    """Every GIF must sit inside a <picture> that offers a still (WCAG 2.2.2, motion over 5 seconds)."""
    text = "\n".join(INLINE_CODE.sub("", line) for _, line in prose_lines(path))
    uncovered = PICTURE.sub(lambda m: "" if offers_still(m.group(0)) else m.group(0), text)
    for raw in GIF_IMAGE.findall(uncovered):
        failures.append(f"{path.relative_to(ROOT)}: animated image without a reduced-motion still: {raw}")


def gif_motion(data: bytes) -> tuple:
    """Read a GIF's blocks. Returns (frames, seconds for one pass, loop count).

    The loop count is None when the file has no NETSCAPE loop extension (it plays once and stops
    on its last frame), 0 when it loops forever, and otherwise the number of repeats.
    Raises ValueError if the bytes are not a well-formed GIF.
    """
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("not a GIF")
    pos = 13
    if data[10] & 0x80:  # global color table
        pos += 3 * 2 ** ((data[10] & 0x07) + 1)

    def skip_sub_blocks(at: int) -> int:
        while data[at]:
            at += data[at] + 1
        return at + 1

    frames, centiseconds, loops, delay = 0, 0, None, 0
    try:
        while True:
            block = data[pos]
            if block == 0x3B:  # trailer
                break
            if block == 0x21:  # extension
                label = data[pos + 1]
                if label == 0xF9:  # graphic control: the delay of the frame that follows
                    delay = struct.unpack_from("<H", data, pos + 4)[0]
                elif label == 0xFF and data[pos + 3 : pos + 14] in (b"NETSCAPE2.0", b"ANIMEXTS1.0"):
                    if data[pos + 14] >= 3 and data[pos + 15] == 1:
                        loops = struct.unpack_from("<H", data, pos + 16)[0]
                pos = skip_sub_blocks(pos + 2)
            elif block == 0x2C:  # image descriptor, then an optional local color table, then the pixels
                packed = data[pos + 9]
                pos += 10
                if packed & 0x80:
                    pos += 3 * 2 ** ((packed & 0x07) + 1)
                pos = skip_sub_blocks(pos + 1)
                frames += 1
                centiseconds += delay if delay >= 2 else 10  # browsers show a 0 or 1 delay as 10
                delay = 0
            else:
                raise ValueError(f"unknown block 0x{block:02x}")
    except (IndexError, struct.error) as error:  # `as` keeps the parentheses, so the host's older python3 parses this
        raise ValueError(f"truncated GIF ({type(error).__name__})") from None
    return frames, centiseconds / 100, loops


def embedded_gifs(path: Path) -> list[str]:
    """Every GIF path that `path` embeds: <img src>, <source srcset> and Markdown images. Not links."""
    found: list[str] = []
    for _, line in prose_lines(path):
        text = INLINE_CODE.sub("", line)
        found += [raw for bang, _, raw in MD_LINK.findall(text) if bang]
        for tag, attrs in HTML_TAG.findall(text):
            given = dict((k.lower(), v) for k, v in ATTR.findall(attrs))
            if tag.lower() == "img" and "src" in given:
                found.append(given["src"])
            elif tag.lower() == "source":
                found += srcset_paths(given.get("srcset", ""))
    return [raw for raw in found if raw.split("?")[0].split("#")[0].lower().endswith(".gif")]


def check_gif_timing(path: Path, failures: list[str]) -> None:
    """An embedded GIF must stop by itself within MAX_MOTION_SECONDS, for every reader."""
    rel = path.relative_to(ROOT)
    for raw in embedded_gifs(path):
        if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I):
            failures.append(f"{rel}: embedded GIF is not in the repository, so its motion cannot be checked: {raw}")
            continue
        target = (path.parent / unquote(raw.split("?")[0].split("#")[0])).resolve()
        if not target.is_file():
            continue  # check_file reports the missing target
        try:
            frames, seconds, loops = gif_motion(target.read_bytes())
        except ValueError as error:
            failures.append(f"{rel}: cannot read embedded GIF {raw}: {error}")
            continue
        if frames < 2:
            continue
        if loops == 0:
            failures.append(f"{rel}: embedded GIF loops forever: {raw} (link to it, or export it to play once)")
            continue
        total = seconds * (1 if loops is None else loops + 1)
        if total > MAX_MOTION_SECONDS:
            failures.append(
                f"{rel}: embedded GIF moves for {total:.1f} s, over the {MAX_MOTION_SECONDS:.0f} s limit: {raw}"
            )


def check_file(path: Path, failures: list[str]) -> int:
    rel = path.relative_to(ROOT)
    checked = 0

    def target(number: int, raw: str) -> None:
        nonlocal checked
        if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I):  # http:, https:, mailto:
            return
        checked += 1
        file_part, _, anchor = raw.partition("#")
        dest = path if not file_part else (path.parent / unquote(file_part.split("?")[0])).resolve()
        if not dest.exists():
            failures.append(f"{rel}:{number} missing target: {raw}")
            return
        if ROOT not in (dest, *dest.parents):
            failures.append(f"{rel}:{number} target outside the repository: {raw}")
            return
        if anchor and dest.suffix == ".md" and unquote(anchor).lower() not in anchors(dest):
            failures.append(f"{rel}:{number} no heading for anchor: {raw}")

    for number, line in prose_lines(path):
        text = INLINE_CODE.sub("", line)
        for bang, alt, raw in MD_LINK.findall(text):
            if bang and not alt.strip():
                failures.append(f"{rel}:{number} image without alt text: {raw}")
            target(number, raw)
        for tag, attrs in HTML_TAG.findall(text):
            found = dict((k.lower(), v) for k, v in ATTR.findall(attrs))
            if tag.lower() == "img":
                if not found.get("alt", "").strip():
                    failures.append(f"{rel}:{number} <img> without alt text")
                if "src" in found:
                    target(number, found["src"])
            elif tag.lower() == "source":
                for candidate in srcset_paths(found.get("srcset", "")):
                    target(number, candidate)
            elif "href" in found:
                target(number, found["href"])
    return checked


def compose_names() -> set[str]:
    """The service, network and volume names declared at the top of compose.yaml."""
    names: set[str] = set()
    section = None
    for line in (ROOT / "compose.yaml").read_text(encoding="utf-8").splitlines():
        top = re.match(r"^([a-z][\w-]*):", line)
        if top:
            section = top.group(1)
            continue
        entry = re.match(r"^  ([a-z][\w-]*):", line)
        if entry and section in {"services", "networks", "volumes"}:
            names.add(entry.group(1))
    return names


def check_diagram(path: Path, failures: list[str]) -> None:
    """The first Mermaid block of `path` must name everything compose.yaml declares."""
    text = path.read_text(encoding="utf-8")
    block = re.search(r"^```mermaid\n(.*?)^```", text, re.S | re.M)
    if not block:
        failures.append(f"{path.relative_to(ROOT)}: no mermaid block")
        return
    for name in sorted(compose_names()):
        if not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", block.group(1)):
            failures.append(f"{path.relative_to(ROOT)}: the container diagram does not name `{name}` from compose.yaml")


def main() -> int:
    failures: list[str] = []
    files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    checked = sum(check_file(f, failures) for f in files)
    for f in files:
        check_motion(f, failures)
        check_gif_timing(f, failures)
    for diagram in (ROOT / "README.md", ROOT / "docs" / "architecture.md"):
        check_diagram(diagram, failures)
    for failure in failures:
        print(failure)
    print(f"check_docs: {len(failures)} failure(s), {checked} relative links and images in {len(files)} files")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""Docs checks for README.md and docs/*.md. Exit 1 if any check fails.

- Every relative link and image path points at a file or folder in the repository.
- Every `#anchor` matches a heading in the file it points at (GitHub's heading ids).
- Every image has alt text.
- The first Mermaid diagram in README.md and in docs/architecture.md names every service,
  network and volume that compose.yaml declares.

External (http, https, mailto) links are not fetched: this runs without network access.

Run: python scripts/check_docs.py   (part of `make lint`)
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
MD_LINK = re.compile(r"(!?)\[((?:[^\]\\]|\\.)*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_TAG = re.compile(r"<(img|a)\b([^>]*)>", re.I)
ATTR = re.compile(r"([a-zA-Z-]+)\s*=\s*\"([^\"]*)\"")
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
    for diagram in (ROOT / "README.md", ROOT / "docs" / "architecture.md"):
        check_diagram(diagram, failures)
    for failure in failures:
        print(failure)
    print(f"check_docs: {len(failures)} failure(s), {checked} relative links and images in {len(files)} files")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

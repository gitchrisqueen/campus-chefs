"""Static checks CHK-01..09 (plan 7.3). Exit 1 if any check fails.

Run: python scripts/static_checks.py
"""

import ast
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIRS = ["config", "core", "accounts", "meals", "bookings", "menuparse"]
failures: list[str] = []


def fail(check: str, msg: str) -> None:
    failures.append(f"{check}: {msg}")


def app_py_files(include_tests: bool = False):
    for d in APP_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            parts = set(p.relative_to(ROOT).parts)
            if "migrations" in parts or (not include_tests and "tests" in parts):
                continue
            yield p


def template_files():
    yield from (ROOT / "templates").rglob("*.html")
    for d in APP_DIRS:
        tdir = ROOT / d / "templates"
        if tdir.exists():
            yield from tdir.rglob("*.html")


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# CHK-01: no hardcoded localhost URLs or the 2008 workspace path
def chk_01() -> None:
    pat = re.compile(r"http://localhost|workspace/")
    files = list(app_py_files()) + list(template_files()) + list((ROOT / "static").rglob("*.css"))
    for p in files:
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                fail("CHK-01", f"{rel(p)}:{n} hardcoded localhost/workspace URL")


# CHK-02: every <img> has alt; every visible input has a label
class _FormA11y(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.labels_for: set[str] = set()
        self.inputs: list[tuple[int, dict]] = []
        self.imgs_without_alt: list[int] = []
        self.label_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label":
            self.label_depth += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        elif tag == "img" and "alt" not in a:
            self.imgs_without_alt.append(self.getpos()[0])
        elif tag in {"input", "select", "textarea"}:
            if a.get("type") in {"hidden", "submit", "button", "reset", "image"}:
                return
            if self.label_depth or a.get("aria-label") or a.get("aria-labelledby"):
                return
            self.inputs.append((self.getpos()[0], a))

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1


def chk_02() -> None:
    for p in template_files():
        parser = _FormA11y()
        parser.feed(p.read_text(encoding="utf-8"))
        for line in parser.imgs_without_alt:
            fail("CHK-02", f"{rel(p)}:{line} <img> without alt")
        for line, a in parser.inputs:
            if a.get("id") not in parser.labels_for:
                fail("CHK-02", f"{rel(p)}:{line} form control without a label")


# CHK-03: app.css parses, and none of the 2008 CSS defects return
def chk_03() -> None:
    import tinycss2

    css_path = ROOT / "static" / "css" / "app.css"
    text = css_path.read_text(encoding="utf-8")
    rules = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)
    errors = [r for r in rules if r.type == "error"]
    for e in errors:
        fail("CHK-03", f"static/css/app.css:{e.source_line} parse error: {e.message}")
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for bad, why in [
        (r"(^|[;{\s])//", "// comment"),
        (r"rightt", "'rightt'"),
        (r"width:\s*1024px", "fixed 1024px"),
    ]:
        if re.search(bad, stripped, re.M):
            fail("CHK-03", f"static/css/app.css contains {why}")
    m = re.search(r'@charset\s+"([^"]+)"', text, re.I)
    if m and m.group(1).upper() != "UTF-8":
        fail("CHK-03", f"static/css/app.css @charset {m.group(1)}")


# CHK-04: no raw SQL entry points in app code
def chk_04() -> None:
    pat = re.compile(r"\.raw\(|\.extra\(|RawSQL|connection\.cursor|cursor\.execute")
    for p in app_py_files():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                fail("CHK-04", f"{rel(p)}:{n} raw SQL")


# CHK-05: no autoescape bypasses
def chk_05() -> None:
    pat = re.compile(r"\|\s*safe\b|mark_safe|autoescape\s+off")
    for p in list(app_py_files()) + list(template_files()):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                fail("CHK-05", f"{rel(p)}:{n} autoescape bypass")


# CHK-06: no committed DB passwords, no empty-password or root DB config
def chk_06() -> None:
    for name in ["compose.yaml", ".env.example"]:
        p = ROOT / name
        if not p.exists():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"(PASSWORD|SECRET|API_KEY)[A-Z_]*\s*[:=]\s*\S", line) and not re.search(
                r"_FILE\s*[:=]|=\s*$|:\s*$", line
            ):
                fail("CHK-06", f"{name}:{n} non-empty secret value")
            if "MYSQL_ALLOW_EMPTY_PASSWORD" in line:
                fail("CHK-06", f"{name}:{n} MYSQL_ALLOW_EMPTY_PASSWORD")
            if re.search(r"(DB_USER|POSTGRES_USER)\s*[:=]\s*[\"']?root\b", line):
                fail("CHK-06", f"{name}:{n} root DB user")


# CHK-07: every ModelForm lists explicit fields
def chk_07() -> None:
    for p in app_py_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != "Meta":
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                if "exclude" in names:
                    fail("CHK-07", f"{rel(p)}:{stmt.lineno} Meta.exclude")
                if "fields" in names and isinstance(stmt.value, ast.Constant) and stmt.value.value == "__all__":
                    fail("CHK-07", f"{rel(p)}:{stmt.lineno} fields = '__all__'")


# CHK-08: pinned actions and images; one Postgres image reference everywhere
def chk_08() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
    pg_refs = set(re.findall(r"postgres:[^\s\"']+", compose))
    for wf in workflows:
        text = wf.read_text(encoding="utf-8")
        pg_refs |= set(re.findall(r"postgres:[^\s\"']+", text))
        for n, line in enumerate(text.splitlines(), 1):
            m = re.search(r"uses:\s*([^\s#]+)", line)
            if m and not re.search(r"@[0-9a-f]{40}$", m.group(1)):
                fail("CHK-08", f"{rel(wf)}:{n} action not pinned to a 40-hex SHA")
            m = re.search(r"\b(?:image:|docker run[^\n]*?)\s*((?:ghcr\.io|aquasec|docker\.io)/[^\s]+)", line)
            if m and "@sha256:" not in m.group(1):
                fail("CHK-08", f"{rel(wf)}:{n} image without digest")
    if len(pg_refs) > 1:
        fail("CHK-08", f"Postgres image references differ: {sorted(pg_refs)}")
    for n, line in enumerate(compose.splitlines(), 1):
        m = re.search(r"^\s*image:\s*(\S+)", line)
        if m and not m.group(1).startswith("campuschefs:") and "@sha256:" not in m.group(1):
            fail("CHK-08", f"compose.yaml:{n} image without digest")


# CHK-09 is codespell (run by `make lint`; legacy/ is skipped in pyproject.toml).


def main() -> int:
    for check in (chk_01, chk_02, chk_03, chk_04, chk_05, chk_06, chk_07, chk_08):
        check()
    for f in failures:
        print(f)
    print(f"static_checks: {len(failures)} failure(s) across CHK-01..08 (CHK-09 = codespell)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

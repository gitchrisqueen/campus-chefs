#!/usr/bin/env bash
# Public-safety denylist scan (plan 5.6, SEC-06).
#
# Scans the working tree (tracked and untracked, not ignored), every file name,
# every commit snapshot in history, and every commit message for the regex in
# PUBLIC_DENYLIST_REGEX (case-insensitive, POSIX ERE).
#
# It prints ONLY locations: path:line, commit:path:line, commit ids and counts.
# It never prints the matched text, because GitHub masks only the whole secret
# string in logs, not each alternative inside the regex.
#
# Exit codes: 0 = no findings, 1 = findings, 2 = misconfigured (fails closed).
set -euo pipefail

re="${PUBLIC_DENYLIST_REGEX:-}"
if [ -z "${re}" ]; then
  echo "denylist: PUBLIC_DENYLIST_REGEX is empty; failing closed" >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"
findings=0

note() {
  echo "denylist: $1"
  findings=$((findings + 1))
}

# 1. Working-tree contents. git grep output is path:line:text; keep path:line only.
while IFS= read -r loc; do
  [ -n "${loc}" ] && note "tree ${loc}"
done < <({ git grep -nIiE --untracked -e "${re}" -- . || true; } | cut -d: -f1,2)

# 2. File names in the working tree (count only: a name would reveal the match).
n="$({ git ls-files --cached --others --exclude-standard || true; } | { grep -ciE -e "${re}" || true; })"
if [ "${n}" -gt 0 ]; then note "tree file names: ${n} match(es), names not printed"; fi

# 3. History: every commit snapshot, contents and file names.
revs="$(git rev-list --all 2>/dev/null || true)"
if [ -n "${revs}" ]; then
  while IFS= read -r loc; do
    [ -n "${loc}" ] && note "history ${loc}"
  done < <({ echo "${revs}" | xargs git grep -nIiE -e "${re}" || true; } | cut -d: -f1-3)

  n="$({ git log --all --name-only --format= || true; } | sort -u | { grep -ciE -e "${re}" || true; })"
  if [ "${n}" -gt 0 ]; then note "history file names: ${n} match(es), names not printed"; fi

  # 4. Commit messages: print short ids only.
  while IFS= read -r c; do
    [ -n "${c}" ] && note "commit message ${c}"
  done < <(git log --all -i -E --grep="${re}" --format=%h || true)
fi

if [ "${findings}" -gt 0 ]; then
  echo "denylist: ${findings} finding(s)"
  exit 1
fi
echo "denylist: 0 findings"

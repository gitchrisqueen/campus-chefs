# legacy/: the 2008 Campus Chefs code

This folder holds the original 2008 PHP 5 code, kept as historical reference for the before/after story.

- **No license is granted for this folder.** The MIT license at the repository root covers the new code only.
- **Do not run or deploy it.** The login can be bypassed with SQL injection, passwords are stored in plain text, and it needs the `mysql_*` extension that PHP 7.0 removed.
- **It is read-only.**
  - `legacy-support/SHA256SUMS` pins every byte.
  - A CI gate fails any PR that touches this folder unless the PR carries the `legacy-change` label.

## What differs from the 2008 files

The code is byte-for-byte the 2008 code except for these changes:

- **Copied by allowlist:** `src/`, `view/`, `css/`, `dbconnection/`, `tests/` and `img/`. The IDE metadata (`.project`, `.settings/`, `.cache/`) was not copied.
- **Personal data replaced:** nine test literals (names, a school and an email) were replaced with `TestName`, `Example College` and `student@example.test`. The file:line list is in `legacy-support/REDACTIONS.md`.
- **Profile photos replaced:** `img/profile_pic.jpg` and `img/profile_pic_small.jpg` are generated placeholders of the same size.
- **Image metadata stripped:** every image was run through `exiftool -all=`, which removed the editor comments.

Line endings and the original ISO-8859-1 encoding are preserved (`.gitattributes` marks this folder `-text`).

`docs/LEGACY-MAP.md` shows where each 2008 file's job lives in the new app.

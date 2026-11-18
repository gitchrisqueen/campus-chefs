# Redactions in legacy/

The original values are not recorded anywhere in this repository. This file lists only each location and what replaced it.

| File:line | Replacement |
|---|---|
| `legacy/src/cook_profile.php:100` | `TestName` |
| `legacy/src/cook_profile.php:116` | `Example College` |
| `legacy/src/cook_profile.php:128` | `student@example.test` |
| `legacy/src/customer_profile.php:91` | `TestName` |
| `legacy/src/customer_profile.php:107` | `Example College` |
| `legacy/src/customer_profile.php:115` | `student@example.test` |
| `legacy/tests/control.php:10` | `TestName` |
| `legacy/tests/control.php:26` | `Example College` |
| `legacy/tests/control.php:38` | `student@example.test` |

| Image | Replacement |
|---|---|
| `legacy/img/profile_pic.jpg` (400×300) | `legacy-support/placeholder.jpg`, a generated placeholder |
| `legacy/img/profile_pic_small.jpg` (200×150) | `legacy-support/placeholder-small.jpg`, a generated placeholder |

All images also had their metadata stripped (`exiftool -all=`). `scripts/check-image-metadata.sh legacy/img` verifies that.

`scripts/denylist.sh` checks that none of the original values appear anywhere in the tree or in the history. The regex it uses is kept outside the repository: in the `PUBLIC_DENYLIST_REGEX` Actions secret, and locally in `~/.config/campuschefs/denylist`.

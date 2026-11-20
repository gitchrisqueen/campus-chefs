# Legacy map: where each 2008 file's job lives in 2026

This map covers every file in `legacy/`. The modules on the right are the targets the plan sets out (`docs/MODERNIZATION_PLAN.md`, section 2.5), and they are built in phases 1–8. Defect numbers refer to plan section 1.3.

## Pages (`legacy/view/`)

| 2008 file | What it did | 2026 home |
|---|---|---|
| `view/welcome.php` | Landing page: mission text, 1-2-3 steps, search box | `core/views.py` home, `templates/core/home.html` |
| `view/register.php` | Registration page shell | `accounts/views.py` register |
| `view/successful.php` | Inserted the user from GET parameters, then said "Thank you" | `accounts/forms.py` + POST view; the defect is covered by REG-01 and REG-08 |
| `view/profile.php` | Profile shell, `$profile_type="cook"` hardcoded | `/me` dashboard and `/cooks/<id>`; LEG-03 covers the hardcoded profile type |
| `view/hi.php` | "Under Construction" target for 6 links | `/how-it-works`, `/safety`, `/privacy`; LEG-07 crawls for "Under Construction", LEG-08 checks every link |
| `view/Cook_Profile.html`, `view/Customer_Profile.html` | Empty templates | Dropped (no content) |

## Includes and classes (`legacy/src/`)

| 2008 file | What it did | 2026 home |
|---|---|---|
| `src/sqlQueries.php` | All SQL, string-concatenated, using `mysql_*` | Django ORM in `accounts/`, `meals/`, `bookings/`; raw SQL banned by CHK-04; LEG-04 covers the swapped campus/profileType insert; AUTH-07 is the SQL-injection regression test |
| `src/login.php` | GET login, compared email to `first_name`, no session, JS redirect | Django auth views over POST + CSRF, session login, rate limit |
| `src/registration_form.php` | Text inputs; TODOs for radios and a drop-down | `accounts/forms.py`: role radio, campus `<select>`, validation |
| `src/cook_main.php` | Cook page, `userID = 1` (`//HACK! fix this`), hardcoded menu | `meals/views.py` cook page from DB rows; LEG-02 covers the hardcoded id, LEG-01 the "Gender" label that showed age |
| `src/customer_main.php` | Empty | `/me` diner panel (bookings) |
| `src/cook_profile.php`, `src/customer_profile.php` | Getter/setter classes, never used | `accounts.User` + `meals.CookProfile` models |
| `src/menu.php` | Breakfast/lunch/dinner arrays, never used | `meals.MenuItem` (meal type × course) |
| `src/search.php` | Echoed the query; form went to `hi.php` | `meals/search.py` + `/search` with htmx |
| `src/header.php`, `src/footer.php`, `src/leftnav.php`, `src/main_corners.php` | Layout includes, hardcoded `localhost` URLs, corner images | `templates/base.html` with `{% url %}` (CHK-01), CSS `border-radius` |

## Other

| 2008 file | What it did | 2026 home |
|---|---|---|
| `dbconnection/db_information.php` | `root` with an empty password, in a web-readable file | Generated secrets read from `*_FILE`, least-privilege DB roles |
| `css/styles.css` | Fixed 1024px layout, invalid `//` comments, `float: rightt` | `static/css/app.css` with tokens, responsive, WCAG 2.2 AA |
| `tests/control.php`, `tests/db_test.php` | Echo scripts with no assertions | pytest suites, about 116 behavioral tests |

## Images (`legacy/img/`)

| Image | Used by 2008 code | 2026 |
|---|---|---|
| `logo2.jpg` | `src/header.php` | Redrawn as `static/img/logo.svg` |
| `welcome1.jpg`, `welcome2.jpg`, `welcome3.jpg` | `view/welcome.php` | The 1-2-3 steps become an HTML/CSS component |
| `headerbottomleft.jpg`, `headerbottomright.jpg`, `newcorner*.jpg` (4) | Header and box corners | Replaced by `border-radius` |
| `profile_pic_small.jpg` | `src/cook_main.php` (now a placeholder) | No photo uploads (plan 1.4) |
| `logo.jpg`, `logo_trans.jpg`, `profile_pic.jpg`, `whiterounded.gif` | **Unused**: no 2008 file references them | Kept for completeness only |

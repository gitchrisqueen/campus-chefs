# Design plan (phase 8a)

This plan covers the visual foundation that every later screen inherits. The tokens live in
`static/css/app.css` (`@layer tokens`) and follow plan section 4.2. UX-01 checks their contrast.

## Ground

- **Subject:** a 2008 student project about home-cooked meals between students, rebuilt in 2026.
- **Readers:** a student deciding whether to try it, and a developer or hiring team judging the rebuild.
- **The home page's one job:** show in one screen what the app does (find a home-cooked meal and chip in
  toward the groceries), and that the 2008 identity survived.

## Palette (token names)

| Role | Light | Dark | Why |
|---|---|---|---|
| `--cc-brand` | `#a40408` | `#b3161b` | The 2008 header red. Dark mode uses a slightly brighter red so it still reads on a dark page |
| `--cc-accent` (links, the italic headline words) | `#a40408` | `#ff9c94` | Brand red fails contrast on a dark page (plan 4.2), so dark mode uses a light coral |
| `--cc-bg` | `#e5ecf3` | `#121417` | The 2008 blue-grey page background |
| `--cc-surface`, `--cc-surface-sunk`, `--cc-border` | white, `#f2f5f9`, `#c9d3de` | `#1c2026`, `#171a1f`, `#343b45` | Panels, the footer and hairlines |
| `--cc-text`, `--cc-muted` | `#1a1a1a`, `#4a5563` | `#eceff3`, `#a9b3bf` | Plan 4.2 values in light mode |
| `--cc-focus` | `#1f5fbf` | `#8ab4f8` | A blue that is clearly not the brand red |
| Badge pairs | share, bring, free, diet, allergen | same names | Each badge carries text, so colour is never the only cue |

## Type

- **Display:** `--cc-font-display`, a system serif stack (Iowan Old Style, Palatino, Georgia). It echoes the
  serif of the 2008 wordmark. Headings, the step numerals and dish names use it.
- **Body:** `--cc-font-body`, the system UI stack.
- **Scale:** a 1.25 modular scale (`--cc-step--1` to `--cc-step-5`). The two largest steps use `clamp()`, so the
  hero headline grows with the viewport.
- No font files ship and nothing loads from a CDN, so there is no font licence to record. The two SVGs in
  `static/img/` are drawn for this repo and use no third-party artwork.

## Layout

Desktop (1280 px):

```
[ Portfolio demo: fictional people and campuses ..................... ]
[ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ red top rule ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ ]
[ (logo plate)                                   Home   How it works ]
[ eyebrow (the only one on the page)                                 ]
[ HOME-COOKED MEALS,                             ┌ example listing ┐ ]
[ made by students                               │ dish            │ ]
[ WHO LOVE TO COOK.                              │ day, time, meal │ ]
[ lede · [Find a meal] (How it works) · chip-in  │ cook, campus    │ ]
[                                                └─────────────────┘ ]
[ How it works  [1] Register. [2] Search. [3] Eat!  Read the details ]
[ ┌ panel: Find a meal [ search input ................... ] (Search) ]
[ ┌ dashed card: Try it in one click     [Try as demo diner] cook ─┐ ]
[ footer: How it works · Safety · Privacy        © 2026 Campus Chefs ]
[                                                  A portfolio demo  ]
```

Phone (390 px): the same order in one column. The listing card sits below the call to action, and the
three steps wrap onto one or two short lines.

Each screen has one filled red button: "Find a meal" in the hero, then "Try as demo diner" in the demo card.
The search button and the hero's "How it works" are outlined.

## The one bold element

The hero: an oversized serif headline with two italic words in the accent colour, next to a tilted example
listing on a red card. The listing is the bold part and it shows the product: a dish, a fictional cook, the
grocery share, the bring-list option and the cook-declared allergens. Everything around it stays quiet: one
red rule, white panels and the 2008 blue-grey.

## Where each choice comes from

There is no moodboard for this brand. Each choice comes from the 2008 artefacts in `legacy/img/` and from plan
section 4:

- **Logo plate** (`static/img/logo.svg`): `logo2.jpg`, the white serif "Campus Chefs" on red, redrawn with
  rounded corners and a covered-dish mark.
- **Numbered step tiles:** `welcome1-3.jpg`, red rounded squares with a white serif numeral. They are now drawn
  by a CSS counter on an `<ol>` (plan 4.3).
- **Page background:** the 2008 `body` colour, `#e5ecf3`.
- **Rounded corners:** `--cc-radius` replaces the six corner JPGs (plan 1.3, #23).

## Anti-generic review

- No gradient hero, no stock photo, no emoji icons, no glassmorphism, and no three-feature-card row with
  icons. The steps are the 2008 steps, not a template block.
- The red is the 2008 red and is used in a few places only: the top rule, the logo, the buttons, the step
  tiles and the listing card.
- **Changed after pass 1:**
  - the step text now lines up across the columns (`align-content: start`);
  - the decorative card no longer causes horizontal scroll at 320 px;
  - the search moved into its own panel with space above it;
  - `/how-it-works` uses a three-card row on desktop instead of one narrow column.
- **Changed after pass 2:** tighter spacing between the search field and its results.
- **Changed after the art-director review (round 1):**
  - one tracked uppercase label per page at most: the hero's "Student meal sharing" stays; the "Three steps",
    "Live search", "Step", "How it works", "My account" and "Join Campus Chefs" eyebrows are gone;
  - the listing card and the footer drop their middle-dot strings for separate lines;
  - the home "How it works" panel is one compact line, because the nav and the hero link to /how-it-works;
  - the demo card moved below the search and has one filled button (diner); the cook option is a text link;
  - the search field fills the panel width with its button at the right edge;
  - on /how-it-works the step cards shrink to their content, and Questions and About sit side by side.

## Form and account pages (design pass 2)

- **Field component** (`templates/partials/field.html`): label, then help, then error, then the control. Django
  links help and error to the control with `aria-describedby` (`<id>_helptext`, `<id>_error`); the error list
  reads "Error:" to screen readers, and the field gets a red rail and a 2px red border, so colour is never the
  only cue.
- **Placeholders** use `--cc-muted`, so their contrast is fixed in both themes. UX-01 already checks
  `--cc-muted` on `--cc-surface`, the input background.
- **Checkboxes** sit in a tinted tile with the box on the first line of the label; the whole tile is the target.
- **Radio group** is a `fieldset` and `legend`; each option is a 52px tile that takes the accent border when
  checked. The cook food-safety box hides with `:has()` once "I want to eat" is chosen (the server still
  checks it).
- **Register** is grouped: Your account, Your profile (first and last name side by side from 40rem), Before you
  start. The group titles are sentence-case serif subheads at `--cc-step-1`, not tracked caps. The password help is one line instead of Django's five-item list.
- **Error summary** lists every problem with a link to its field, has `role="alert"`, and takes focus (A11Y-02).
- **Danger** (`/me/delete`): a red-ruled callout says "You cannot undo this." and the button is a solid dark red
  (light) or inverted coral (dark). New tokens: `--cc-input-border`, `--cc-danger*`; UX-01 checks them.
- **Log out** is a reset button that reads as a nav item, with the same hover and focus ring as the links.
- **Demo login** is a dashed invitation card: "Try it in one click", one line, a diner button (primary) and a
  cook text link. The cook link is a POST button styled as a link, so its accessible name stays "Try as demo cook".
- **/me** has an initials avatar (plan 4.4: initials only), the public name as the heading, a role badge, a
  ruled profile list and an empty-bookings state with a "Find a meal" button.
- **Changed after pass 1:** the diner badge was invisible on the page background (now on white with a border);
  the phone nav orphaned "Log out" (tighter nav padding below 40rem); the /me phone buttons were ragged (now
  full width); the radio legend sat tight on its tiles; the login demo card now matches the login card padding.
- **Changed after pass 2:** an optional select beside a field with an error stretched taller (rows now align on
  the bottom edge).

## Booking, search and kitchen screens (design pass 3, phase 8b)

- **Offering page:** two balanced columns. Left: dishes, the allergen notice, then "Chip in". Right: when and
  where, then the booking panel. The booking form shows only the fields the chosen way of chipping in needs.
- **Search filters** use the same field partial as every other form, and the allergen filter uses the checkbox
  tiles: two columns on a phone, as many 10rem columns as fit on a desktop, every row the same height.
- **Kitchen:** quiet actions ("Cancel meal", "Delete") sit close to the "Edit" button instead of spreading across
  the row.
- **Changed after pass 1:** the allergen tiles were one per row on a phone (now two), the tiles in the second
  row were shorter than the first (now equal rows), and the cook's panel on their own offering was headed
  "Request a seat" (now "Your meal").

- **Later screens follow the same rules (phase 8b):** the booking, offering, kitchen, cook, search, set-up and
  `/me` screens lose their repeated eyebrows (the booking status is now the status badge), their middle-dot
  strings become separate lines or commas ("Sat, 9:30"), and "Add a dish" is outlined so "Open a meal" is the one
  filled button. Browser tab titles keep their " · ".

## Open points

- The error summary lists errors in the form's field order, which differs from the grouped visual order on
  `/register` (email, password first). Each item links to its field, so this is cosmetic.

- Screenshots are taken in the Linux tests container, so the system serif there is the container's fallback
  serif, not Iowan Old Style or Palatino. On macOS and Windows the display face is warmer.
- In the container's sans-serif fallback, `<strong>` inside body text renders close to the regular weight.
  Check it on a desktop browser during the UX review.

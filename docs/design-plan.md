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
[ demo banner ...................................................... ]
[ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ red top rule ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ ]
[ (logo plate)                                   Home   How it works ]
[ eyebrow                                                            ]
[ HOME-COOKED MEALS,                             ┌ example listing ┐ ]
[ made by students                               │ dish, cook, $   │ ]
[ WHO LOVE TO COOK.                              │ badges, seats   │ ]
[ lede · [Find a meal] [How it works] · chip-in  └─────────────────┘ ]
[ ┌ panel: How it works  [1] Register.  [2] Search.  [3] Eat! ─────┐ ]
[ ┌ panel: Find a meal   [ search input ......... ] [Search] ──────┐ ]
[ footer: How it works · Safety · Privacy               © 2008–2026 ]
```

Phone (390 px): the same order in one column. The listing card sits below the call to action, and each step
puts its numeral tile beside its text.

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

## Open points

- Screenshots are taken in the Linux tests container, so the system serif there is the container's fallback
  serif, not Iowan Old Style or Palatino. On macOS and Windows the display face is warmer.
- In the container's sans-serif fallback, `<strong>` inside body text renders close to the regular weight.
  Check it on a desktop browser during the UX review.

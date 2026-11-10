---
name: Telephone dashboard
description: A neutral viewing surface for judging a photograph against its own copies.
colors:
  ground: "#e6e6e6"
  viewing: "#d6d6d6"
  surface: "#fbfbfb"
  surface-2: "#f0f0f0"
  ink: "#111111"
  ink-2: "#3d3d3d"
  muted: "#636363"
  line: "#cdcdcd"
  line-strong: "#8f8f8f"
  rail: "#161616"
  rail-ink: "#f2f2f2"
  rail-muted: "#a9a9a9"
  station-platform: "#2a78d6"
  station-reader: "#eb6834"
  station-painter: "#1baf7a"
  status-good: "#0ca30c"
  status-warning: "#fab219"
  status-critical: "#d03b3b"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "1.75rem"
    fontWeight: 680
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 660
    lineHeight: 1.25
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  none: "0px"
  control: "6px"
  pill: "999px"
spacing:
  tight: "8px"
  group: "16px"
  section: "40px"
  page: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    height: "38px"
    padding: "0 16px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "38px"
    padding: "0 16px"
  sheet:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.control}"
  patch:
    rounded: "{rounded.none}"
    size: "12px"
---

# Telephone dashboard design

This file records the look of the dashboard in `telephone/dashboard/static/`. It was written by
hand from the built interface on 10 November 2026. Impeccable's own documenter could not run in
that session, so treat the token block above as the source of truth and the stylesheet
(`app.css`) as its implementation. It does not describe the public site in `web/`, which has not
been redesigned yet.

## Overview

The world is the photographer's calibration target: the grey card, the step wedge and the colour
chart that are photographed to check a print. The page is a neutral viewing surface, so that two
versions of a photograph can be compared without the interface tinting the comparison. The
measuring scale is drawn on the page as a step wedge wherever a drift number appears. That wedge
is the one signature element.

The scene that decides light or dark: a student at a laptop in daylight, sometimes mirrored to a
projector. So the design is light first. A dark variant exists for people whose system asks for
one, with its own values in `app.css`.

## Colors

Neutrals carry no colour cast, on purpose. This is the one place where the usual advice to tint
neutrals is refused: a tinted ground would bias how the photographs look.

- `ground` is the page. `viewing` is one step darker and is used only behind photographs.
- `surface` is for sheets that hold forms, tables and charts.
- `rail` is the black frame of the target and holds the navigation.
- Colour appears only as flat patches with one meaning each: `station-platform`,
  `station-reader`, `station-painter`. The three were checked together with the dataviz palette
  validator for every kind of colour vision, in both themes. A fourth station hue fails that
  check, so the camera station uses `ink-2`.
- Status colours (`status-good`, `status-warning`, `status-critical`) always come with an icon
  and a word.
- Charts are drawn in ink. A chart never borrows a station colour.

## Typography

One family, the system sans, for everything. A fixed rem scale with small steps: 0.75, 0.8125,
0.9375, 1.0625, 1.1875 and 1.75rem. Numbers in tables and axes use tabular figures. Monospace is
used for file paths, key names and chain ids, which are code.

## Layout

A fixed left rail of 232px and one main column no wider than 1080px. Prose stays under about 68
characters a line. Sections are separated by 40px, with more space above a heading than below it.
Below 900px the rail becomes a top bar with the five destinations in one row. Below 560px
side-by-side pictures stack. The comparison of original and generation runs edge to edge on the
`viewing` grey.

## Elevation & Depth

Flat. Depth comes from the three neutral layers and hairline borders. The only shadow is under a
toast.

## Shapes

Photographs, patches and the step wedge have square corners, like the objects they come from.
Controls and sheets use a 6px radius. Tags are pills.

## Components

- Step wedge: twenty grey steps from near white to near black, a marker with a light ring so it
  reads on every step, and four named bands underneath (same, close, far, different). The
  left end is the original and the right end is a different photograph. The compact form drops
  the labels and is always followed by the position in words.
- Patch: a 12px square of a station colour, always next to the station's name.
- Buttons: primary is solid ink, secondary is outlined, quiet has no border. One primary button
  per view. Pressing scales to 0.97.
- Sheet: a white panel with a hairline border, for forms, tables and charts. Sheets are not
  nested.
- Tag and status line: an icon plus a word. "Simulation" is the one tag that must never be
  dropped from a simulated result.
- Charts: hand-written SVG. 2px ink line, hairline grid, a tooltip on hover, the last value
  labelled, and a table of the same numbers close by.

Motion is limited to state: the press on a button, the progress bar, and a toast arriving.
Durations stay under 300ms and `prefers-reduced-motion` removes the movement.

## Do's and Don'ts

- Do put what a number means next to the number.
- Do label every simulated picture and description as a simulation.
- Do show the original next to anything it is compared with.
- Don't tint the neutrals or place photographs on a coloured ground.
- Don't use a station colour for anything except its station.
- Don't add a chart library, an icon font, emoji, or imagery that is not a pipeline output or one
  of the author's photographs.
- Don't animate a picture as it changes between generations. The change itself is the subject.

# Product

<!-- impeccable:product-schema 1 -->

This is the product record for the Telephone website in `web/`. It was written on 17 November 2026
from the repository and from three answers Bardia gave that day (audience, what to do about the
look, what would feel wrong). It holds facts about the product. It does not choose colours, type
or layout.

## Platform

web

## Users

1. Ordinary visitors come first. Someone with no technical background opens a link once, on a
   phone or a laptop. They have not read the brief and do not know what a JPEG, a model or a
   metric is. Their job is to understand, in about a minute, what happened to one photograph and
   why that matters.
2. Photographers come second. They make pictures and want to know what the systems that carry
   their work keep and what they drop.
3. Tutors marking the Experimentation Portfolio for 5IMAG022W come third. They read for evidence
   of experimentation. The "How it works" page and the research log serve them; the first page
   does not have to.

## Product Purpose

The site is the practical outcome of Telephone. It shows one of my photographs being passed along
again and again, and what is left of it after each pass.

It exists to make one idea visible: a photograph matters because it is specific (this place, this
light, this person), and the systems that carry photographs keep what is typical and drop what is
specific.

It has worked when a first-time visitor can say in their own words what was kept and what was
lost, without having read the name of a metric.

## Positioning

Every picture on the site is either a photograph I took or the real output of the pipeline run on
that photograph. Every statement about what survived comes from a saved run that anyone can
re-run from the repository. Nothing is an illustration of what might happen.

## Operating Context

- A static site (Vite, React 19, TypeScript) served from GitHub Pages. No server sits behind the
  published site.
- It reads a static JSON export written by `telephone export`. Whatever the site shows was put in
  that export.
- Visited once, by link, often on a phone. Also shown on a projector in the 1 December
  presentation and linked from the final submission.

## Capabilities and Constraints

- Charts are hand-written SVG that read the static export. No chart library.
- No AI-generated or stock imagery as decoration. The only images are my photographs and pipeline
  outputs. An image an AI station produced is a result and is labelled as one.
- If output from mock providers ever appears, it is labelled "simulation".
- A visitor's own photograph never leaves their browser. The "try your own photo" step runs on
  the visitor's device; nothing is uploaded and nothing is stored (decided 17 November 2026).
- Photographs in `data/originals/private/` are never exported.
- Technical measurements (SSIM, CLIP distance, LPIPS and the rest) live on the "How it works"
  page. The first page uses everyday words.
- Words the site uses:

  | In the code | On the site |
  |---|---|
  | generation | pass ("pass 3") |
  | chain | journey, or just "this photograph" |
  | run the loop | pass it on |
  | drift | how far it has moved from the original |
  | survival | what is left, shown as "still here" and "gone" |
  | caption and regenerate | a machine describes it and another machine redraws it; this is the only loop called a "retelling" |

- Not available yet: results from the describe-and-redraw loop. There are no API keys, so there
  are no machine-written descriptions and no redrawn pictures. The site has to be truthful and
  complete without them and must not show placeholders that look like results.
- Not available yet: my own one-sentence caption for each photograph.
- The look: keep the current look of the site (confirmed 17 November 2026). The Impeccable engine
  could not run in the cloud session that day, so no new visual world was created. A new look is a
  later decision, made by running `/impeccable` where its engine can run.

## Brand Commitments

- Name: Telephone, after the children's game. Author: Bardia Nasab.
- Voice: first person and plain. "My photographs", "I passed it on".
- It must not feel like an advert for an AI product. The site questions these systems; it does not
  sell them.
- It must not be a wall of text. The photographs lead.

## Evidence on Hand

- Six photographs of mine in `data/originals/`, with a table of what each shows in
  `docs/BRIEF.md`.
- Experiment 1 (re-upload only), saved in `data/results/exp01_compression.jsonl`: all the change
  happens on the first upload, then the loop sits still.
- The screenshot-and-forward loop (`exp07_screenshot_loop`) and the place line-up
  (`data/places.yaml`, `telephone place-test`) were being built and run on 17 November 2026. Use
  their saved results once they exist; do not describe results that have not been saved.
- No machine captions, no redrawn images, no survival-form answers, no author captions. Do not
  invent any of them.

## Product Principles

1. The photograph leads and the words stay short.
2. Say what was measured in everyday words, and never claim more than the run shows.
3. One thing to do on the first screen.
4. Question the systems; do not sell them.
5. Nothing of the visitor's leaves their device.

## Accessibility & Inclusion

- Respect `prefers-reduced-motion`. No scroll-jacking and no parallax on photographs.
- Everything works with a keyboard and has a visible focus state.
- Every photograph has alt text that says what it shows, taken from my own description of it.
- Nothing is told by colour alone: "still here" and "gone" differ in words and shape as well.

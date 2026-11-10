# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Two surfaces, two stacks.

- The dashboard (`telephone dashboard`) is built into the Python package: a FastAPI server plus
  hand-written HTML, CSS and JavaScript modules with no build step. Confirmed by Bardia on
  10 November 2026, so that anyone who has installed the Python tool can open it with one command
  and without Node.
- The public site in `web/` is Vite + React 19 + TypeScript, deployed to GitHub Pages as static
  files. It existed before this record.

## Users

- Bardia Nasab, a photography student at the University of Westminster who is comfortable with
  Python and Git and new to image-similarity metrics. He runs the experiments and has to explain
  every part of the project out loud.
- Anyone who clones the repository (confirmed 10 November 2026): recruiters for applied AI,
  forward deployed engineer and solutions architect roles, and classmates. They start the
  dashboard with no help and no knowledge of the project.
- Tutors and assessors on 5IMAG022W The Networked Photograph, who see the work in tutorials and a
  10-minute presentation.

## Product Purpose

Telephone plays the children's game with a photograph. A photo is passed again and again through
the systems that handle pictures online (a platform that recompresses it, an AI reader that
describes it, an AI painter that redraws it from the description), and every trip round the loop
is measured: how far the picture has drifted from the original, and which facts about it are still
true. The research question is what a photograph keeps and loses, and whether the identity of a
place survives.

The dashboard exists so that running an experiment and reading its result need no terminal and no
prior knowledge. Success is a first-time visitor who can start a run, watch it, and say in plain
words what the result means.

## Positioning

A small, reproducible evaluation harness that is also an art project: every image shown is the
author's own photograph or a pipeline output of it, every number can be traced to a ledger row,
and paid model calls sit behind a hard spend cap.

## Operating Context

- Runs on the user's own machine. The dashboard is a local server bound to the loopback address;
  it is not part of the public website.
- Used at a laptop, in daylight, sometimes mirrored to a projector in a seminar room.
- Six photographs in `data/originals/`. Results live in a local SQLite ledger; committed
  snapshots live in `data/results/`.
- As of 10 November 2026 there are no API keys, so only the compression experiment and
  simulations can run.

## Capabilities and Constraints

- Vocabulary is fixed by `docs/BRIEF.md`: station (Platform, Reader, Painter), chain, generation,
  drift, survival. Generation 0 is the original.
- Total API spend cap of $15. A paid run is never started without showing the estimated cost
  first and getting a confirmation.
- Runs on mock providers are simulations and are always labelled as such.
- Photographs under `data/originals/private/` are never shown, exported or served.
- Visitors cannot upload photographs through any interface.
- No AI-generated or stock imagery in the interface. The only images are the author's photographs
  and pipeline outputs.
- Charts are hand-written SVG. No chart library.
- Motion respects `prefers-reduced-motion`. No scroll-jacking and no parallax on photographs.
- API keys are never typed into or displayed by the dashboard.

## Evidence on Hand

- Experiment 1 (compression only): 24 chains, 504 generations, saved in
  `data/results/exp01_compression.jsonl`, with figures in `docs/tutorial-10nov/figures/`.
- No real describe-and-redraw results exist yet. Nothing may be presented as one.

## Product Principles

1. The experiments come first. An interface never replaces or overstates them.
2. Plain words before numbers. Every number sits next to what it means.
3. Honest by construction: simulations are labelled, failed runs are kept, costs are stated before
   they are incurred.
4. One command to start, nothing to configure for the free experiments.

## Accessibility & Inclusion

WCAG 2.1 AA as the working target (inferred, not yet confirmed by Bardia). Charts never rely on
colour alone, following the colour-blind-safe rule already used for the project's figures.

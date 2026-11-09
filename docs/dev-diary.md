# Development diary

One entry per step, dated. What we tried, what happened, what failed, what we changed and why,
with the path of a figure or screenshot where there is one. The module brief rewards iteration,
failed tests and changes of direction, so this file is the raw material for those slides.

## 2026-11-09: the first version was too technical, so we are simplifying

A previous session built a complete first version: the Python pipeline with five station kinds and
six providers, six experiment definitions, a figure renderer, a static website with eight pages, a
FastAPI service with capped live runs, a deck builder, CI and a Pages deployment. It runs end to
end on mock providers with no keys.

The problem is that I cannot explain all of it, and the website does far more than the project
needs: compare views, a labelling page, a live-run page, experiment pages full of numbers. The
marks are for the research and the log. So the order of work is now: brief first, then the
compression experiment on my own photos for the tutorial, then bug fixes and usability, then a
small Gemini loop, then saving real results as examples. The website is simplified last, down to
one photo, its generations, a plain list of what survived and one drift line.

An audit of the core loop also found six bugs (chain identity ignores which models were used, the
spend cap resets every process, Gemini is always costed at zero, the run ledger is committed to
git, the JSONL copy of the ledger drifts from the SQLite one, and experiment 6's folder placeholder
is never filled). They are fixed in step 2, each with a failing test first.

## 2026-11-09: the upload had already compressed my photos

The six photographs in `data/originals/` reached the repository through the Claude app's upload.
Checking them with Pillow shows every one at 2000 pixels on the long edge (the abstract crop is
460) with zero EXIF tags. So the upload resized them and stripped their metadata before the
project touched them. Generation 0 has already been through one platform.

Decision: record it here and in the brief, keep going with these files for the tutorial, and
consider replacing them with full-quality originals from my phone later. If they are replaced, the
experiments are re-run; compression runs are deterministic and take minutes.

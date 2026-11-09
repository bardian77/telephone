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

## 2026-11-09: step 1, the compression loop on my own photographs

What we tried. Experiment 1 as defined in `experiments/exp01_compression.yaml`: six photographs,
four platform presets, twenty generations each, with the survival form switched off because
there is no vision-model key yet. Metrics computed locally: SSIM (scikit-image), colour-histogram
distance, file size, CLIP ViT-B/32 cosine distance and LPIPS.

What happened. 24 chains, 504 generations, nothing spent. Every chain does all of its changing on
the first pass and then sits still: SSIM and CLIP distance at generation 20 equal their values at
generation 1 to three decimals, 13 chains become byte-identical between generations 3 and 13, and
the other 11 differ by at most 231 bytes per generation with SSIM to the previous generation at or
above 0.9998. Normal presets: SSIM above 0.97, CLIP distance 0.01 to 0.03. Harsh preset (512 px,
quality 30): SSIM 0.83 to 0.93, CLIP distance 0.06 to 0.12. The vertical Bologna photo loses the
most under every preset; the 460 px abstract crop is never resized and still loses 3 to 9 percent
SSIM. Figures: `docs/tutorial-10nov/figures/contact_*.jpg` and `drift_*.png`, plus the standard
set in `data/figures/exp01_compression/`. Rows: `data/results/exp01_compression.jsonl`.

What failed, in order.

- The cloud container had none of the project's dependencies installed and its network refused
  the hosts that serve CLIP and LPIPS weights. A separate cloud environment for this repository
  now allows them. Two more surprises on the way: the PyTorch wheel index redirects downloads to a
  second host, so the CPU-only wheel could not be fetched and the ordinary PyPI build is used
  instead; and Hugging Face redirects the CLIP weight file to `us.aws.cdn.hf.co`, found by
  following the redirect by hand, which had to be allowed separately.
- Experiment 1 could not run without an Anthropic key, because the YAML declares a vision
  extractor and the command had no way to skip it. Added `--no-extract`, test first.
- The run ledger was committed to git and every run changed it. It is now local state, ignored by
  git; real results are saved with `telephone save-results` as a sorted JSONL file that can be
  committed and reloaded.
- With CLIP unavailable the drift chart was still drawn from the single hard-coded generation-0
  point. A chain now needs two points before it counts as a curve.
- The SSIM fallback used without scikit-image is a single global term, not a windowed SSIM; the
  docstring said otherwise. Corrected, and scikit-image is installed so the real metric is used.
- The session's worker restarted twice mid-run. Work was committed and pushed early after that.

What we changed and why. The first run was done without CLIP and LPIPS; once the weights could be
downloaded, the ledger rows for experiment 1 were deleted and the run repeated so every row
carries all the metrics (station outputs came from the cache, only the metrics were recomputed).
The figure script says "same picture from g1" rather than "still changing" for chains whose
files differ by a few bytes, because the first wording was true of the bytes and false of the
picture. The four preset colours were checked with the palette audit in the scientific
visualization skill: all clear the graphical contrast threshold on white; four of the six pairs
are weak in grayscale, so every preset also has its own marker and a direct label.

Change of direction for later. Re-uploading at a fixed size and quality does not decay a
photograph; re-sampling does. Experiment 1 needs a variant that moves the pixel grid every pass,
as Ashton's screenshots did, to see cumulative loss without any AI. Not run yet.

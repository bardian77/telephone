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

## 2026-11-09: step 2, the audited bugs and a command line a person can use

What we tried. The six bugs from the audit of the core loop, each with a test written to fail
first, then the usability list: one `--mock` flag, a `telephone doctor` command, one-line errors
instead of tracebacks, commands that work from any folder, one place for model defaults, a
glossary in the README, and a private folder for photographs that must never be published.

What happened. The test suite went from 25 tests at the start of the day to 54, all passing.
A chain is now resumed only from ledger rows whose station configuration matches a fingerprint,
so a run on mock providers can never be continued as a real one. The spend cap counts every paid
call ever made, from an append-only log in the ledger, and both run commands refuse to start
when the estimate does not fit in what is left. Gemini is costed at list price unless
`GEMINI_FREE_TIER=1` says otherwise. The ledger is local; `save-results` writes the rows of one
experiment as a sorted file that is committed. Experiment 6's folder placeholder is filled per
image. `telephone doctor` says what is installed, which keys are set, how much has been spent,
and for every experiment what it still needs or how it can run now.

What failed or changed on the way.

- The plan said to seed the spend cap from the generation rows. The verification pass found that
  a re-run replaces a row and loses its earlier cost, while a cache hit copies an old cost into a
  new row, so that sum is wrong in both directions. The cap now counts a separate append-only
  spend log that every paid call writes.
- The plan said to namespace mock runs with a double underscore. The chain-id parser splits on
  double underscores, so the suffix is a hyphen: `exp02_caption_length-mock`.
- The previous code assumed Gemini was free. With list price as the default, the estimates for
  experiments 2 to 5 went up and one test's bound had to move.
- The PyTorch wheel index redirects to a second host, so the CPU-only wheel could not be
  installed in the cloud environment; the ordinary PyPI build works on the CPU and is used
  instead. Hugging Face redirects weight downloads to `us.aws.cdn.hf.co`, found by following the
  redirect by hand.
- The session's worker restarted five times during the day. Committing and pushing after every
  batch kept the work safe.

What's next. Step 3: a free Gemini key through the secure form, then a few describe-and-redraw
loops with the estimated cost stated first. Step 4: save real results as preloaded examples and
label any mock output that reaches the site as a simulation. For experiment 1, the variant that
moves the pixel grid every pass, to test whether re-sampling is what makes decay add up.

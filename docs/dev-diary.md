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

Review pass, same day. A review workflow checked the step 2 diff on four lenses. One finding was
confirmed and fixed with a test: because settings now anchor on the project root, the test suite
had started reading the project's `.env`, so a developer with a real key there could have made the
tests call a paid provider. Tests now set `TELEPHONE_ENV_FILE=""` and never read a dotenv file.
The usage limit cut the verification of the other findings short; two cheap ones were fixed by
hand (physical frame folders were resolved against the current directory; a stale "free key"
message). The rest are recorded here as unverified follow-ups rather than acted on blind:
`--mock` decides the `-mock` suffix per chain, so a mixed experiment could split in two; a
replaced photograph under the same filename is resumed from the old generation 0; any
`ValueError` stops a whole experiment; a misspelled platform preset silently falls back to
Instagram; the lifetime cap, the physical station error and the API's private-stem refusal are
not exercised through the CLI or API tests; `log/build_deck.py` still assumes the repo root as
the working directory; `save-results` includes private photos' rows in the committed file.

## 2026-11-10: a dashboard, so the project can be run and read without the terminal

What we tried. I had run experiment 1 but could not say what its output meant, and every step
needed a terminal command. So this session built a dashboard: `telephone dashboard` opens a page
in the browser that lists the experiments in plain words, starts a run with the cost stated
first, shows each generation as it arrives, and explains each result. I chose three things by
answering questions: anyone who clones the repository should be able to use it, it is built into
the Python tool with no Node and no build step, and it looks like a photographer's calibration
target (neutral grey ground, drift drawn as a marker on a grey step wedge).

What happened. The backend was written test first: 19 new tests, 74 in total, all on mock
providers or compression only. Experiment 1 was then run again from the dashboard on all six
photographs: 24 chains, 504 pictures, 7 minutes 20 seconds, nothing spent. All 504 output hashes
match the saved snapshot in `data/results/exp01_compression.jsonl`, so the run is reproducible
byte for byte. A practice run on the five synthetic images took 21 seconds. An automated
accessibility scan (axe) reports no violations on nine pages in light and dark.

What the dashboard showed that the 10 November summary got slightly wrong. The summary says the
WhatsApp and Instagram presets move CLIP distance by 0.01 to 0.03, and that every chain does all
of its changing on the first upload. Per preset the final CLIP distances are: Instagram 0.009 to
0.017, WhatsApp 0.008 to 0.039, screenshot then WhatsApp 0.022 to 0.093, harsh 0.057 to 0.118.
And 22 of the 24 chains settle on the first upload. The other two are the Dolomites landscape
and the self-portrait under screenshot then WhatsApp, which keep moving for two or three uploads
(0.020 to 0.032, and 0.078 to 0.093) before they stop. The self-portrait under that preset drifts
as far as some harsh chains while its SSIM stays at 0.991. The summary file has not been edited.

What failed or changed on the way.

- The Impeccable and Superpowers plugins are enabled in the project settings but were not
  installed in the cloud session. Impeccable's playbooks were read from its GitHub repository
  instead. Its launcher is a downloaded program, and the session's safety layer refused to run
  it, so there was no dice roll of visual directions, no design detector, and `DESIGN.md` was
  written by hand. The direction was chosen from three options through the question tool.
  Test-driven development was followed by hand.
- The first file-size sentence compared the last generation with generation 0, which is stored
  as a lossless PNG copy and is several times larger than the photograph's own JPEG. It read
  "0% of the original file". It now compares with the photograph's own file.
- A thumbnail sometimes arrived broken, because one request could read a preview file that
  another request was still writing. Previews are now written whole and moved into place.
- A fourth station colour (violet, for the camera station) failed the colour-vision check next
  to the Platform blue, so the camera station is drawn in neutral ink.
- Each new generation used to fade in during a run. With a picture arriving about once a second
  that became a pulse, and the animation review removed it.
- Hidden elements were still visible because a layout rule overrode the `hidden` attribute.
- A separate reviewer, given only the screenshots and the brief, sent the first version back for
  fixes. Its main point was that my band names overclaimed: a simulated picture that looked
  nothing like its original was labelled "Same picture, worn. Clearly the same photograph", from
  a CLIP score alone. The bands now say what the comparison model scored (same, close, far,
  different) and the page says next to the wedge that they are a rule of thumb. It also caught
  that the run list showed only one version of each loop, that the Start page used the word
  chain before explaining it, and that the smallest text on the page was the explanations.

What's next. The dashboard runs the AI experiments only as simulations until there is a key, so
step 3 (a Gemini key and a small real loop) is unchanged. A single custom chain (one photograph,
any list of stations) cannot be started from the dashboard yet; `telephone run-chain` still does
that. The public website has not been touched.

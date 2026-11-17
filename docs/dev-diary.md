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

## 2026-11-17: the why, two experiments with no key, and four instruments that were wrong

What we tried. Bardia asked what the project is for, and how to make it usable by ordinary people
and by photographers. The answer became the project's reason: a photograph matters because it is
specific, and the systems that carry photographs keep what is typical and drop what is specific.
Everything after that was "what can be done towards that with no key": the screenshot loop that
was already planned, a first measurement of whether a place survives, a rewrite of the brief and
the README, a kit for the two experiments only Bardia can do, and the website cut down to one
plain-language page.

What was built, each with tests written first (the suite went from 55 tests to 245; three of
them need the real CLIP model and are skipped unless asked for).

- A `screenshot` station and `experiments/exp07_screenshot_loop.yaml`: five journeys of 40 passes.
- The place line-up: `data/places.yaml`, `telephone/metrics/place.py`, `telephone place-test`.
  The file of line-ups was committed on its own before any result (commit 54539ba), and a test
  holds its fingerprint.
- `telephone detail-test` and `telephone/metrics/detail.py`: each pass compared at its own size
  with the same part of the original, following the crop.
- `telephone export-site` and the new site in `web/`.

What happened. Experiment 7 ran on the six photographs: 30 chains, 1230 files, nothing spent.
Figures are in `docs/tutorial-17nov/figures/`, the rows in `data/results/exp07_screenshot_loop*.jsonl`.
The numbers below are for the five full-size photographs at pass 40; the 460 px reflection crop
is reported apart because the app enlarges it.

| Journey | Settled at pass | Fine detail left | Frame left |
|---|---|---|---|
| Upload again (control) | 4 to 5 | 91 to 95% | all |
| Screenshot, one phone (bicubic) | 14 to 18 | 75 to 86% | all |
| Screenshot, one phone (bilinear) | 25 to 38; one not in 40 | 39 to 53% | all |
| A different phone each pass | not in 40 | 71 to 86% | all |
| A careless crop each pass | not in 40 | 16 to 30% | 53 to 73% |

On the 512 px SSIM the first four journeys are all between 0.948 and 0.995, which is why it was
replaced. The control is byte for byte experiment 1's Instagram chain for passes 0 to 20 (126 of
126 files).

The place line-up. On the originals the true place is first of 12 for all six photographs, with
probability 0.72 (Bologna), 0.99 (Barbican lake), 0.98 (Seddon House), 0.60 (larches), 0.30
(self-portrait) and 0.60 (reflection crop). Under the upload, one-phone and many-phones journeys
it stays first for every photograph at every pass. Under the careless crop Bologna stays first
while its probability falls from 0.72 to 0.44, the self-portrait loses first place on 22 passes
and the reflection crop on 34. Under experiment 1's harsh preset one upload narrows the true
place's margin over the next candidate for all six photographs and loses it for three: Bologna
comes second to Padua, the self-portrait's Dolomites come fourth (its best ladder rung moves from
"the Alps" to "the mountains"), and the reflection crop comes second to Thamesmead. The margins
are thousandths of a cosine similarity, so this is a first reading and not a result to lean on.

Two different photographs of mine are 0.17 to 0.54 apart in CLIP distance (median 0.47). The two
closest pairs are the two Barbican photographs (0.17) and the two Dolomites photographs (0.22).

What failed, in order.

- The first plan was run as a workflow of several agents. The container restarted in the middle
  and killed it. The files survived on disk, so nothing was lost, but from then on every step was
  committed and pushed as soon as its tests passed. Later the usage limit stopped two more
  workflows mid-way. The rest was done directly, one step at a time.
- The Impeccable engine could not run in the cloud session (it downloads and runs its own
  program, and the session's rules refused that). Its written rules were followed by hand, the
  look was kept, and Bardia confirmed that choice. A new look still needs `/impeccable` on a
  machine where it can run. Superpowers was not installed either; test-first was done by hand.
- The exact-crop screenshot chain was expected to keep decaying. It settled too. Then the
  many-phones chain was expected to keep decaying. It keeps changing, but it levels off within a
  few points of the one-phone chain. What compounds is a crop that is slightly off, which shifts
  the picture against the pixel grid every pass.
- The 512 px SSIM could not see any of that. Reviewers measured about 40% of the fine detail
  gone on a chain it scored 0.993.
- The first fine-detail measure (variance of a Laplacian) counted the speckle that saving adds.
  A chain that saved at quality 80 and then 60 scored 1.83 while its SSIM fell to 0.86. It was
  replaced by a projection on the reference's fine detail (`detail_kept`, 0.98 for that picture),
  with the total kept beside it (`detail_energy`, 1.42). Both experiments were measured again.
- The loose-crop numbers measured the cropping. `detail-test` now tracks the crop box; across
  all 1230 rows the registration check found a shift of (0, 0).
- CLIP had been built with GELU where OpenAI's weights were trained with QuickGELU. The library
  only warned. The loader now forces the right activation and refuses a mismatch, and result
  labels carry the build (`ViT-B-32/openai/quickgelu/open_clip-4.2.2`). Experiment 1 was run
  again: all 504 files are byte for byte the ones from 9 November, SSIM and LPIPS are unchanged,
  and the CLIP distances moved (Instagram and WhatsApp presets 0.008 to 0.078 where the 10
  November summary says 0.01 to 0.03; harsh 0.057 to 0.114). The first results are kept in
  `docs/evidence/`, and the 10 November summary carries a dated correction.
- The first place calibration was scored on the mis-built model. It showed the reflection crop
  near chance (rank 2, 0.10) and the self-portrait unplaced (rank 3, 0.12), which looked like
  the control working. On the corrected model both rank first (0.60 and 0.30). The control
  prediction failed and is recorded as failed in `data/places.yaml`. No line-up was edited.
- The first rule for "settled" was the first quiet pass. In the many-phones chain the 1080 px
  phone changes nothing, so that rule said "settled at pass 9" for a chain that was still
  changing at pass 40. The rule is now: no later pass changes it, for at least three passes.
- On the site, the first layout put the photograph and the "Pass it on" button below the first
  screen on a phone, and quick presses were lost because the state was read back from the
  address. Both were found by the screenshot check and fixed.

What we changed and why. The brief has the new reason, a sharper question with five smaller
ones, and the experiments in story order; two of the old experiments are set aside. The site's
first page uses "pass", says what is left in sentences, and never shows a metric name; the
measurements and their limits are on "How it works". The older technical pages are still there
under `/lab` but are not linked from the published site. "Try it with your own photo" runs in
the visitor's browser, which changes the old rule "visitors cannot upload anything" into
"a visitor's photograph never leaves their browser".

Not acted on, kept here as follow-ups. From the first review: seven behaviours in the place
tests that can be broken without a test failing; CLIP sees only the central square of a picture
(for the self-portrait the result depends on which square it is shown); the three line-ups are
not equally hard. From before: `save-results` would include a private photograph's rows; a
replaced photograph under the same filename is resumed from the old generation 0. New: the loose
crop uses one sequence of crops for all six photographs, so they are not six independent tries;
the screenshot step is my model of a phone, and a real screenshot cropped by hand has not been
compared with it; the browser version of "try your own photo" blurs more than the pipeline does,
because browsers resize differently.

What's next. Bardia confirms the place labels and writes a caption for each photograph. A Gemini
key, then describe and redraw, with the survival form split into specific and generic facts and
a record of what the machine adds. The human telephone chain and the physical loop, which need
Bardia. The deck is rebuilt from `log/outline.md`.

# Telephone

**What does a photograph keep and lose as it passes repeatedly through the systems that circulate and interpret it?**

A photograph goes round a loop. A platform recompresses it, a vision-language model describes it, a text-to-image model redraws it from the description, and the result goes round again. At every generation the pipeline records how far the picture has drifted from the original and which of its machine-readable attributes are still alive.

This is the Experimentation Portfolio for *5IMAG022W The Networked Photograph* (University of Westminster) and, deliberately, a small production-shaped evaluation harness: provider abstraction, structured outputs, content-addressed caching, a hard spend cap, a run ledger, a static site built from that ledger, and a validation of the automated measures against hand labels.

- Site: https://bardian77.github.io/telephone/ (static, no server, never spends money)
- Research log: `log/outline.md` → `python log/build_deck.py` → `log/build/telephone_log.pdf`
- Method and references: the About page of the site, or `log/outline.md` slides 2 to 6

## The loop

| station | what it does | default system |
|---|---|---|
| `platform` | resize to a platform's maximum edge, re-encode JPEG at its quality, strip metadata | Pillow, presets `instagram` `whatsapp` `twitter` `facebook` `messenger` `harsh` `gentle` `screenshot` |
| `caption` | describe the image in `short` (20 words), `detailed` (150 words) or `literal` (noun inventory) mode | Claude Sonnet 5.5 (`claude-sonnet-5-5`) |
| `regenerate` | text-to-image from the current caption | Gemini 2.5 Flash Image (billed at list price unless `GEMINI_FREE_TIER=1`); FLUX.1 schnell on Cloudflare Workers AI (free tier, seeded) |
| `extract` | fill a fixed JSON schema (objects, people count, visible text, setting, lighting, mood, dominant colours, camera angle, reads-as-photograph) | Claude Sonnet 5.5 with structured outputs |
| `physical` | pick up a phone photograph of a screen showing the previous generation | your camera |

A *chain* is one original image plus an ordered list of stations, repeated for N generations (default 12). An *experiment* is a YAML file in `experiments/` that expands to many chains (images × variants × repeats).

## Glossary

One plain sentence for each word the rest of this README leans on.

- **Station**: one step a picture goes through. `platform` squeezes it the way an upload does, `caption` has a vision model describe it, `regenerate` has an image model redraw it from that description, `extract` fills in the survival form, `physical` picks up a photo of a screen.
- **Chain**: one photograph plus an ordered list of stations, run round and round.
- **Generation**: one trip round the loop. Generation 0 is the original; generation 1 is what comes out after one trip.
- **Variant**: one named list of stations inside an experiment file, such as the `harsh` preset in experiment 1. An experiment runs every variant on every photograph.
- **Repeat**: the same chain run again with a different seed, to see how much a non-deterministic model varies.
- **Extractor**: the vision model that fills in the survival form (objects, people, text, setting, lighting, mood, colours, camera angle, photograph or not) at every generation. Experiments name it separately from the stations; `--no-extract` switches it off.
- **Drift**: how far a generation has moved from the original, as a number. CLIP distance and colour-histogram distance for every chain, SSIM and LPIPS where pixel structure still means something.
- **Survival**: which answers on the survival form still match generation 0, and the first generation at which each one stops matching.
- **CLIP**: an image-recognition model that turns a picture into a list of numbers describing what it shows. The distance between two pictures is 0 when they are identical; two different photographs from this project are about 0.50 apart.
- **SSIM**: structural similarity, a comparison of pixel structure. 1 means identical; one Instagram-style re-save scores about 0.99.
- **LPIPS**: a learned measure of how different two pictures look, trained on human judgements. 0 means identical.
- **Mock provider**: a fake stand-in that costs nothing, used by the tests, CI and `--mock`. Its output is a simulation, not a result, and is filed under `<experiment>-mock`.

## Measurement

- **Drift.** Cosine distance between CLIP ViT-B/32 embeddings (CPU) of generation *n* and generation 0, and to generation *n−1*. A colour-histogram (Hellinger) distance that needs no model is always recorded too. SSIM and LPIPS for compression-only chains, where pixel geometry still means something.
- **Survival.** Each extracted field is compared with generation 0 under rules stated in `telephone/metrics/survival.py` (set Jaccard for objects and colours, exact match for counts and categories, normalised token overlap for text, fuzzy match for setting and mood). The result per chain is *the first generation where each field fails*.
- **Machine readability.** OCR word count (tesseract, if installed) and frontal-face count (OpenCV Haar cascade).
- **Validation.** The site's Label page collects my own 1-to-5 "same picture?" score and per-field survival calls on a fixed sample of 60 pairs; `telephone validate` reports Spearman correlation against the distances and precision / recall of the automated survival calls.

Every proxy is a proxy. The README of a results-bearing repo should say where they disagree with a person; that table lives in `analysis/validation/report.md` once labels exist.

## Experiments

| id | question | variable |
|---|---|---|
| `exp01_compression` | does compression alone move a photograph, and do the metrics behave? | platform preset |
| `exp02_caption_length` | does a longer description keep more alive? | caption mode: short / detailed / literal |
| `exp03_system_swap` | does drift belong to a model or to the process? | captioner × generator (2 × 2) |
| `exp04_photo_types` | what dies first for portraits, street, landscape, text, abstract? | photo type (filename prefix), 3 repeats |
| `exp05_mixed_chains` | when compression and AI steps are interleaved, which does the damage? | station order |
| `exp06_physical` | what does a camera pointed at a screen keep that a platform or a model does not? | physical loop |
| `exp00_smoke` | does everything run with no keys and no spend? | mock providers, synthetic fixtures |

## Quick start

```bash
git clone https://github.com/bardian77/telephone && cd telephone
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[all]"                      # torch CPU: add --index-url https://download.pytorch.org/whl/cpu for torch/torchvision first
cp .env.example .env                            # add ANTHROPIC_API_KEY and GEMINI_API_KEY (key from aistudio.google.com)
telephone doctor                                # what is installed, which keys are set, what can run now
telephone run-experiment exp01 --no-extract     # compression only on your photographs; needs no key
telephone save-results exp01_compression        # data/results/<experiment>.jsonl, safe to commit
telephone render exp01_compression && telephone export --experiment exp01_compression
cd web && npm ci && npm run dev                 # site on http://localhost:5173 showing the export
```

Commands work from any folder: paths anchor on the project root (the folder with `pyproject.toml` and `experiments/`, or `TELEPHONE_ROOT`).

Everything also runs with no keys on the offline stand-ins, which is what the tests and CI do:

```bash
telephone make-fixtures                         # five synthetic test images; only exp00 uses them
telephone run-experiment exp00 --no-clip        # the smoke test, mock providers, zero spend
telephone run-experiment exp02 --mock --no-clip # any experiment on mocks; filed under exp02_caption_length-mock
```

Then with keys and your own photographs in `data/originals/` (see the README there for naming and consent):

```bash
telephone run-experiment exp01 --dry-run        # chains, paid calls, cost estimate; runs nothing
telephone run-experiment exp01                  # resumable; cached stations cost nothing
telephone run-chain --image data/originals/street_01.jpg --stations "platform:instagram,caption:detailed,regenerate" --generations 12
telephone list && telephone cost
python analysis/figures.py                      # every figure for the log
telephone export                                # web/public/data for the site
python log/build_deck.py                        # the research log as pptx + pdf
```

Keys live in `.env` at the project root or in the environment, never in the repo. `TELEPHONE_SPEND_CAP_USD` (default 15) is a lifetime cap: every paid call is logged in the ledger, and a call that would take the total over the cap is refused before it is made. Gemini is costed at list price unless `GEMINI_FREE_TIER=1` says your key is on the free tier.

## Design choices and tradeoffs

- **Ledger first.** One SQLite row per generation (`telephone/ledger.py`) with models, versions, prompt, seed, every metric, cost and latency, plus an append-only log of every paid call. Figures, the site and the API are views of it. The ledger is local state; `telephone save-results` writes an experiment's rows as sorted JSONL under `data/results/`, which is committed and can be reloaded with `load-results`. A chain is resumed only from rows whose station configuration matches its fingerprint, so a run on mock providers or another model is never continued as a real one.
- **Content-addressed cache.** A station's output is keyed on the input image hash, the station config, the model and the seed (`telephone/cache.py`). Repeated views, re-renders and resumed runs never call a provider. The cache is also what makes `--dry-run` estimates honest about what will actually be paid.
- **Cost is reserved before the call, committed after.** `telephone/cost.py` tracks paid cost and list price separately, so free-tier runs still report what a commercial reproduction would cost.
- **Structured outputs over prose parsing.** The survival schema is a pydantic model passed to the Anthropic SDK's `messages.parse`; a malformed reading is a refusal, not a silently broken row.
- **Refusals are data.** A provider declining an image is recorded as a station error, the chain stops, and the failed run is kept and shown on the site under "Failed runs (kept)". The brief asks for failed tests; the ledger keeps them by construction.
- **Free tiers over seeds.** Gemini's image model has no seed control, so headline experiments run 3 repeats and report the spread. Cloudflare's FLUX schnell is seeded and free, and is the second generator in the swap experiment. Replicate and OpenAI adapters exist but are optional and paid.
- **Static site, optional API.** The site is built from a JSON export and works on GitHub Pages with no backend. `api/main.py` serves the same export plus `/live`, which is off unless `TELEPHONE_LIVE=1`, rate-limited per IP, capped per day and cached.
- **CPU only.** CLIP ViT-B/32 runs in about 0.1 s per image on a laptop CPU. Where torch or the weights are unavailable, CLIP is skipped with a warning and the histogram distance stands in, so the pipeline never blocks on a model download.

## Known failure modes

- The histogram distance saturates for regenerated images (anything redrawn from text is a different palette); it is a sanity curve for compression chains, not a substitute for CLIP.
- SSIM and LPIPS compare pixel structure; for regenerated images they measure "is this a different picture", which is always yes.
- The survival rules are mine. Fuzzy matching on `setting` and `mood` can call two different places alive if they share a word; the validation table is where that shows up.
- Free-tier quotas change without notice (Gemini: roughly 15 requests per minute and a daily cap). The rate limiter leaves headroom; a 429 ends the chain with an error row rather than retrying forever.
- Vision models sometimes decline images of people. Those rows stay in the ledger and are discussed in the log.
- Provider model IDs and prices in `telephone/cost.py` are a snapshot and will drift.

## Repository map

```
telephone/            pipeline package: config, models, ledger, cache, cost, stations/, providers/, metrics/, chain, experiments, render, export, cli
experiments/          YAML definitions of the six experiments plus the mock smoke test
api/                  FastAPI service (static export + optional capped live runs)
web/                  Vite + React + TypeScript site; web/public/data/sample is a committed export of the smoke test
analysis/             figures.py and the validation folder
log/                  research log outline and deck builder
data/                 originals/ (your photographs, committed; originals/private/ is not), results/ (committed snapshots of real runs), figures/, and the local-only ledger, runs/ and cache/
tests/                offline tests on mock providers
```

## Ethics

Only photographs I took are used as starting images. People appear only with consent, and anything under `data/originals/private/` is processed only when named explicitly and is never exported to the site or served by the API. Visitors cannot upload images; the live demo runs on my photographs only, so nothing from a visitor is ever stored. Free-tier providers may use inputs to improve their services, which is another reason only my own images go through them. Generated images keep whatever watermark the provider adds.

## Licence

Code: MIT. Photographs, generated images and figures: CC BY-NC 4.0. See `LICENSE`.

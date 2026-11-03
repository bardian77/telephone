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
| `regenerate` | text-to-image from the current caption | Gemini 2.5 Flash Image (free tier); FLUX.1 schnell on Cloudflare Workers AI (free tier, seeded) |
| `extract` | fill a fixed JSON schema (objects, people count, visible text, setting, lighting, mood, dominant colours, camera angle, reads-as-photograph) | Claude Sonnet 5.5 with structured outputs |
| `physical` | pick up a phone photograph of a screen showing the previous generation | your camera |

A *chain* is one original image plus an ordered list of stations, repeated for N generations (default 12). An *experiment* is a YAML file in `experiments/` that expands to many chains (images × variants × repeats).

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
cp .env.example .env                            # add ANTHROPIC_API_KEY and GEMINI_API_KEY (free at aistudio.google.com)
telephone make-fixtures                         # synthetic test images
telephone run-experiment exp00 --no-clip        # whole pipeline on mocks, zero spend
telephone render exp00_smoke && telephone export --experiment exp00_smoke
cd web && npm ci && npm run dev                 # site on http://localhost:5173 showing the export
```

Then with your own photographs in `data/originals/` (see the README there for naming and consent):

```bash
telephone run-experiment exp01 --dry-run        # chains, paid calls, cost estimate; runs nothing
telephone run-experiment exp01                  # resumable; cached stations cost nothing
telephone run-chain --image data/originals/street_01.jpg --stations "platform:instagram,caption:detailed,regenerate" --generations 12
telephone list && telephone cost
python analysis/figures.py                      # every figure for the log
telephone export                                # web/public/data for the site
python log/build_deck.py                        # the research log as pptx + pdf
```

Keys live in `.env` or the environment, never in the repo. `TELEPHONE_SPEND_CAP_USD` (default 20) stops a process before the call that would exceed it.

## Design choices and tradeoffs

- **Ledger first.** One SQLite + JSONL row per generation (`telephone/ledger.py`) with models, versions, prompt, seed, every metric, cost and latency. Figures, the site and the API are views of it. Re-running anything is idempotent.
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
data/                 originals/ (yours, gitignored), fixtures/, runs/ and cache/ (gitignored), figures/
tests/                offline tests on mock providers
```

## Ethics

Only photographs I took are used as starting images. People appear only with consent, and anything marked in `data/originals/private.txt` is processed but never exported to the site. Visitors cannot upload images; the live demo runs on my photographs only, so nothing from a visitor is ever stored. Free-tier providers may use inputs to improve their services, which is another reason only my own images go through them. Generated images keep whatever watermark the provider adds.

## Licence

Code: MIT. Photographs, generated images and figures: CC BY-NC 4.0. See `LICENSE`.

# Research and Experimentation Log: outline

5IMAG022W The Networked Photograph · Experimentation Portfolio · Bardia Nasab
Target: 16 slides, exported as PDF. Figures come from `data/figures/` (run `python analysis/figures.py`).
Every slide has a *claim* (one sentence) and *evidence* (a figure, a contact sheet, a number, a quote).
Slides marked [RESULTS] are filled from real runs; the deck builder leaves a placeholder until then.

---

## 1. Title
- **Telephone.** What does a photograph keep and lose as it passes repeatedly through the systems that circulate and interpret it?
- One-line method: a photograph goes round a loop (platform recompression → machine description → regeneration from the description) and every generation is measured for drift and survival.
- Visual: a 1 x 7 contact sheet of one real chain (g0 … g12). Figure: `exp02_caption_length/contact_sheets/<best chain>.png`

## 2. Context A: recursion as method
- Pete Ashton, *I Am Sitting in Stagram* (2015): one photograph reposted to Instagram 90 times, each repost a screenshot of the last. Alvin Lucier, *I Am Sitting in a Room* (1969): a voice re-recorded until only the room remains.
- Why it matters: both treat the *channel* as the subject. The image is a probe; the degradation is a portrait of the system. Telephone adds two channels Ashton did not have: the describing machine and the drawing machine.
- Visual: still from Ashton's sequence (credit) beside my generation 0 and generation 12.

## 3. Context B: circulation degrades, recursion collapses
- Hito Steyerl, *In Defense of the Poor Image* (2009): the compressed, copied, low-resolution image is not a failed image but the image that actually circulates.
- Shumailov et al., *AI models collapse when trained on recursively generated data*, Nature (2024): recursive generation forgets the tails of the distribution first; the typical survives, the specific dies.
- Why it matters: it predicts *what* should die first in my chains (the unusual detail, the exact text, the particular person) and what should survive (the generic scene). That prediction is testable with the survival metric.

## 4. Context C: machine-readable images
- Trevor Paglen, *Invisible Images (Your Pictures Are Looking at You)* (2016); Crawford and Paglen, *Excavating AI* (2019): most images are now made for and read by machines; the labels machines attach are partial and loaded.
- Thomas Ruff, *jpegs* (2004 onwards); Rosa Menkman, *Glitch Studies Manifesto* (2010): compression as aesthetic.
- Why it matters: my caption station *is* a machine reading, and the regenerate station is that reading made visible. The compression-only baseline keeps Ruff's question in the frame.

## 5. Initial idea and the networked photograph
- The photograph today is rarely seen once; it is uploaded, recompressed, auto-described (alt text, moderation, search), and increasingly redrawn (editing tools, feeds of generated images). Each of those is a lossy translation.
- The loop diagram: three stations, output feeds input, N generations.
- What changed from the first idea: started as "caption and regenerate", then added the compression baseline (to separate the channel from the model), the survival schema (because an embedding distance says *how far*, not *what*), and the physical loop (to put a camera back in the work).

## 6. Method: measurement and the ledger
- Drift: CLIP ViT-B/32 cosine distance to generation 0; colour-histogram distance; SSIM and LPIPS for compression-only chains.
- Survival: one JSON schema (objects, people count, visible text, setting, lighting, mood, dominant colours, camera angle, reads-as-photograph) extracted every generation by Claude Sonnet 5.5 with structured outputs; compared with generation 0 under stated rules; "first generation where the field fails".
- Machine readability: OCR words, face count.
- Reproducibility: every generation is a ledger row (models, versions, prompt, seed, cost, metrics); every station output is cached by content hash; a hard spend cap; the whole pipeline runs offline on mock providers.
- Visual: table of the ledger row + screenshot of `telephone run-experiment exp02 --dry-run`.

## 7. [RESULTS] Experiment 1: compression only
- Claim to test: metrics behave sensibly, and compression alone barely moves the photograph.
- Figures: `exp01_compression/ssim_to_g0_by_variant.png`, `exp01_compression/clip_dist_to_g0_by_variant.png`, one contact sheet (harsh preset, g0/g5/g20).
- Note what happened: SSIM falls then plateaus (JPEG fixed point); CLIP distance stays small; survival stays near 100%. Anything else means a bug.

## 8. [RESULTS] Experiment 2: short vs detailed captions
- Claim to test: a 150-word description keeps more alive than a 20-word one.
- Figures: `exp02_caption_length/clip_dist_to_g0_by_variant.png`, `exp02_caption_length/survival_fraction_by_variant.png`, contact sheets for the same photograph through short / detailed / literal.
- Read out: where the chains diverge, and which attributes the short caption loses first (median first-failure table).

## 9. [RESULTS] Experiment 3: swap the systems
- Claim to test: drift belongs to the process, not to one model.
- Figure: `exp03_system_swap/clip_dist_to_g0_by_variant.png` (four cells), heatmaps per cell.
- Read out: do the four cells agree in shape? Which captioner hallucinates text? Which generator "genre-shifts" (photo → illustration)?

## 10. [RESULTS] Experiment 4: what survives per photo type
- Claim to test: portraits lose identity but keep "a person"; text images lose exact text first; landscapes are the most stable.
- Figures: `exp04_photo_types/survival_type_*.png` (five heatmaps as a grid), `clip_dist_to_g0_by_type.png`.
- Read out: median first-failure generation per field per type.

## 11. [RESULTS] Experiment 5 or 6: mixed chains / the physical loop
- Mixed: does compression before captioning change what the captioner sees? Figure: `exp05_mixed_chains/clip_dist_to_g0_by_variant.png`.
- Physical: a phone photographing a screen for 10 generations; the same metrics. Contact sheet + `cross_experiment_drift.png` to put compression, AI and camera on one axis.

## 12. Failures and changes of direction (kept)
- Refusals (model declined to describe a face), hallucinated text, captions that drifted genre ("a painting of…"), the mock-provider smoke test that exposed a cache key bug, the first histogram metric that saturated, rate limits on the free tier, runs stopped by the spend cap.
- Each one as: what happened → what it told me → what changed. Pull from the ledger's `error` column and the experiment pages' "Failed runs (kept)".

## 13. Validation: do the proxies agree with me?
- 60 hand-labelled pairs from the Label page. Spearman between my 1-to-5 similarity and CLIP / histogram / SSIM; per-attribute agreement, precision, recall for survival.
- Figure: table from `analysis/validation/report.md`. Be honest about where the automated reading and I disagree (and which of us was wrong).

## 14. Final outcome: the website
- Screenshots: chain player with scrubber, drift curve and survival table; compare view; experiment page with first-failure table.
- How a visitor uses it: choose a photograph → choose a chain → scrub → see what died when. Live runs behind a cap.
- URL + fallback (screen recording, PDF contact sheets).

## 15. Reflection
- What a photograph keeps: the generic (setting, mood, "a person"). What it loses: the specific (this person, these words, this light). The loop is a machine for turning photographs into their captions.
- Limits: embedding distance and model-extracted labels are proxies; the survival schema is my choice of what counts; free-tier generators have no seeds so repeats matter.
- Ethics: own photographs only; consent for people; nothing uploaded by visitors is stored; free-tier data use acknowledged; provider watermarks kept.
- Resume angle (one line, if asked): a reproducible evaluation harness with provider abstraction, structured outputs, caching, hard cost control and an honest validation.

## 16. References and repository
- Ashton (2015); Lucier (1969); Steyerl (2009); Shumailov et al. (2024); Paglen (2016); Crawford and Paglen (2019); Ruff (2004–); Menkman (2010); Radford et al., CLIP (2021); Wang et al., SSIM (2004); Zhang et al., LPIPS (2018).
- github.com/bardian77/telephone · site URL · models and versions used (from the ledger).

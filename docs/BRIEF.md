# Telephone: the brief

Read this first. It says what the project is, what has been decided, what we are doing and in
what order. It is written so that Bardia can explain every part of it out loud. Technical words
are defined the first time they appear.

## What the project is

In the children's game Telephone, a sentence is whispered from one person to the next and comes
out the other end changed. This project plays that game with a photograph. The photo is passed
again and again through the systems that handle pictures online, and each pass is measured.

There are three kinds of station a photo can pass through:

1. Platform. Does what an upload to Instagram or WhatsApp does: shrinks the picture, re-saves it
   as a JPEG at the platform's quality, and strips the hidden metadata (camera, date, location).
2. Reader. An AI vision model writes a description of the picture in words.
3. Painter. An AI image model draws a new picture from that description alone.

A chain is one of my photographs plus a chosen list of stations, run round and round. Each trip
round the loop is one generation. Generation 0 is the original; generation 1 is what comes out
after one trip; and so on, usually to generation 12 or 20.

At every generation two things are measured:

- Drift: how far the picture has moved from the original, as a number.
- Survival: which facts about the picture are still there. A vision model fills in a fixed form
  for every generation (objects, number of people, visible text, setting, lighting, mood, main
  colours, camera angle, whether it still looks like a photograph). Each answer is compared with
  the answer for generation 0, so we can say which fact died first.

The platform-only chain is the baseline: it shows how much damage plain compression does before
any AI is involved.

## The research question

What does a photograph keep and lose as it passes repeatedly through the systems that circulate
and interpret it?

The theme I want to follow with my own photos: does the identity of a place survive? Do the
Bologna porticoes stay Bologna, and does the Barbican stay the Barbican, or do they turn into a
generic "European street" and a generic "concrete building"?

## Why it counts

This is the Experimentation Portfolio for 5IMAG022W The Networked Photograph at the University of
Westminster, worth 50% of the module. It is also meant to work as a resume project for applied AI,
forward deployed engineer and solutions architect roles: a small, reproducible evaluation harness
with a cost cap, a run ledger and an honest validation.

The submission has two parts, handed in together:

1. The practical outcome, in any suitable format.
2. A research and experimentation log: 10 to 20 slides exported as a PDF, with a contextual
   reference and why it matters, the initial idea, evidence of technical experimentation, evidence
   of development including failed tests and changes of direction, and the final outcome with a
   short reflection.

The marks reward the research and the log more than the website. The website must never replace
the experiments.

## Deadlines

| Date | What |
|---|---|
| 10 Nov 2026 | 1-1 tutorial. Show a first real loop on a few of my own photos. |
| 17 Nov 2026 | Second tutorial. |
| 24 Nov 2026 | Experiments 1 to 3 done, with metrics. |
| 1 Dec 2026 | 10-minute work-in-progress presentation. |
| 5 Jan 2027, 1pm | Final submission on Blackboard: practical outcome plus the log as a PDF. |

## The photographs

All six are mine and live in `data/originals/`. The word before the first underscore is the photo
type, which experiment 4 groups by.

| File | What it shows |
|---|---|
| `street_bologna_portici_01.jpg` | Bologna porticoes at sunset, warm terracotta, small figures. The only vertical photo. |
| `street_barbican_lake_01.jpg` | Barbican lake, brutalist columns, reflections, fountain, a coot. |
| `landscape_dolomites_larches_01.jpg` | Dolomites, golden larches, blue sky, sun flare, a small car. |
| `portrait_dolomites_self_01.jpg` | Me with the car, ultra-wide lens, curved horizon. I consent to my own image being processed and published. |
| `text_barbican_seddon_house_01.jpg` | Barbican, low angle, overcast, "Seddon House" and "No Cycling / No Skateboarding" signs in small text. |
| `abstract_barbican_reflection_01.jpg` | Crop of the lake photo, a column reflected in rippled water. 460 pixels wide on purpose. |

One thing to remember about them: they reached this repository through the Claude app's upload,
which resized them to 2000 pixels on the long edge and removed all their metadata. So generation 0
has already been through one platform. This is recorded in the dev diary. I may replace them with
full-quality originals from my phone later; if I do, the experiments are re-run.

Photos that must stay private go in `data/originals/private/`. That folder is never committed
and never exported to the website.

## Where things stand (10 November 2026)

A previous session built a working first version: the Python pipeline, six experiment definitions,
figures, a website and a deck builder. It works, but it is too technical to explain, and the
website does far too much. We are simplifying: experiments and the log come first, the website
comes last and will show one photo, its generations, a plain list of what survived and one simple
drift line.

Steps 0, 1 and 2 were done on 9 November (details in `docs/dev-diary.md`). Experiment 1 ran on all
six photographs: under a fixed platform preset all of the change happens on the first upload and
the loop then sits still, which is itself a finding. The six audited bugs are fixed with tests,
`telephone doctor` reports what can run, and every command works from any folder.

On 10 November a dashboard was added, so the project can be run and read without the terminal:
`telephone dashboard` opens it in the browser. It lists the experiments in plain words, runs them
with the cost stated first, shows each generation as it arrives, and explains every result
(pictures next to the original, drift on a step wedge, the survival form). It is a local tool in
`telephone/dashboard/` and is separate from the public website, which is still to be simplified.
Its design facts are in `PRODUCT.md` and `DESIGN.md`.

There are no API keys yet. That decides the order of work:

- Runs without keys: the compression-only experiment (experiment 1), and the local measurements
  (SSIM, colour histogram, file size, and CLIP distance and LPIPS when their model weights can be
  downloaded).
- Needs keys: anything with a Reader or Painter station, and the survival form.

Rules about money and keys:

- Total API spend cap for the whole project: $15 (assumed, see the end of this file). The
  software refuses a call that would go over it.
- No paid call is ever made without saying the estimated cost first.
- Keys are never pasted into chat. When one is needed, it goes in through the secure credential
  form, and from there into the environment as `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`.
- Tests and CI only ever use mock providers (fake stand-ins that cost nothing). If mock output
  ever appears in public, it is labelled "simulation".

## The plan

Step 0 (this document). Write the brief and start the dev diary and the tutor questions.

Step 1 (for the 10 November tutorial, no keys). Run experiment 1, the compression-only loop, on
all six photos for 20 generations under four platform presets. Measure locally. Make one contact
sheet and one drift curve per photo and a half-page spoken summary. Everything goes in
`docs/tutorial-10nov/`.

Step 2. Fix the bugs found in the audit of the core loop, each with a failing test first, and the
usability problems: one `--mock` flag, a `telephone doctor` command that says what can run, clear
one-line errors instead of tracebacks, commands that work from any folder, one place for model
defaults, a plain-language glossary in the README, and the private folder.

Step 3. Get a free Google AI Studio key for Gemini, with a walkthrough. Run a few
describe-and-redraw loops on Gemini only. The plan and the estimated cost come first. Note: the
free tier may let Google use what is sent to it, which is one more reason only my own photos go in.

Step 4. Save the real results from steps 1 and 3 as preloaded examples, so the website and the
deck always have real content even with no keys.

Later phases, not started:

- Experiments 2 to 6 (caption length, swapping the reader and painter, photo types, mixed chains,
  the physical loop of photographing a screen) and the hand-labelled validation of the metrics.
- Figures for the deck.
- Simplify the website: a visitor picks a photo, watches the generations, sees a plain list of
  what survived and was lost, and one drift line. All technical metrics move to a separate "How it
  works" page. Starts with `/impeccable init`.
- Fill the deck and the README.

## Which skill does what

Claude Code uses named skills for different kinds of work. The session says which one it is using
before each task.

| Work | Skill |
|---|---|
| Fixing bugs and adding commands in the Python code | Superpowers test-driven-development (write the failing test first), systematic-debugging when something misbehaves |
| Figures: contact sheets, drift curves | scientific-visualization (colour-blind safe, readable on a slide) |
| Anything that calls the Anthropic SDK | claude-api. Model IDs, the spend cap and rate limits do not change without asking |
| Prose for people: this brief, the README, the diary, the tutor summary | humanizer. It never changes a number, a metric name or a citation |
| The website's look | Impeccable only; its design brief is the source of truth |
| Motion on the website | emil-design-eng and review-animations |
| Checking the website before shipping | web-design-guidelines |
| Screenshots of the website | webapp-testing |
| Inspecting the deck | pptx. The deck is built by `log/build_deck.py`, never edited by hand |

Planning is done in plan mode. Superpowers brainstorming and `/impeccable shape` are not run in
the same session as plan mode, because each wants to lead.

## References

Already in the deck outline (`log/outline.md`):

- Pete Ashton, *I Am Sitting in Stagram* (2015). One photo reposted to Instagram 90 times, each
  repost a screenshot of the last. The closest precedent for the compression loop.
- Alvin Lucier, *I Am Sitting in a Room* (1969). A voice re-recorded in a room until only the
  room's resonance is left. The original "channel becomes the subject" piece.
- Hito Steyerl, *In Defense of the Poor Image* (2009). The compressed, copied, low-resolution
  image is the image that actually circulates.
- Shumailov et al., *AI models collapse when trained on recursively generated data*, Nature
  (2024). Recursive generation forgets the rare details first. This predicts what should die first
  in my chains.
- Trevor Paglen, *Invisible Images (Your Pictures Are Looking at You)* (2016). Most images are now
  made for and read by machines.
- Kate Crawford and Trevor Paglen, *Excavating AI* (2019). The labels machines attach to images
  are partial and loaded.
- Thomas Ruff, *jpegs* (2004 onwards). Compression as a visual subject.
- Rosa Menkman, *Glitch Studies Manifesto* (2010). Compression artefacts as aesthetic.

Suggested by Claude, not yet checked by Bardia. Check each before citing it:

- Ted Chiang, "ChatGPT Is a Blurry JPEG of the Web", The New Yorker (2023). Argues that a language
  model is a lossy compression of its training data. Gives the project its plainest metaphor and
  links the compression loop to the AI loop.
- Taryn Simon and Aaron Swartz, *Image Atlas* (2012). Shows the top image search results for one
  word in different countries. Relevant to whether a machine's idea of "Bologna" or "Barbican" is a
  specific place or an average.
- Clement Valla, *Postcards from Google Earth* (2010 onwards). Collected glitches where Google
  Earth drapes photographs over the wrong terrain. Automated image systems producing a place that
  does not exist.
- Penelope Umbrico, *Suns from Sunsets from Flickr* (2006 onwards). Thousands of near-identical
  sunset photos pulled from Flickr. The generic image that circulation produces, which is what my
  chains may converge to.
- Jon Rafman, *9-Eyes* (2008 onwards). Street View frames chosen by a person from a machine's
  automatic survey of places. Machine-captured place versus human looking.
- Mishka Henner, *Dutch Landscapes* (2011). Dutch government sites censored in satellite imagery
  with bold polygons. Deliberate degradation of a place's image by a system.

## Ethics

- Only photographs I took are used as starting images.
- The self-portrait is mine and I consent to its processing and publication. People in the street
  photos are small and not identifiable.
- Visitors to the website cannot upload anything, so nothing from a visitor is ever stored.
- Free-tier AI services may use what is sent to them. Only my own photos go through them. The
  exact terms for Gemini's free tier are checked and written here in step 3.
- Generated images keep whatever watermark the provider adds.

## Assumptions to confirm

Four details were left as placeholders in the instructions. These values are assumed until
Bardia confirms or changes them:

1. Total API spend cap: $15.
2. Time available: about 10 hours a week.
3. Level: comfortable with Python and Git, new to image-similarity metrics such as CLIP, SSIM and
   LPIPS. Explanations in this repository are pitched there.
4. References already liked: none yet.

# Telephone: the brief

Read this first. It says what the project is, why it matters, what has been decided, what we are
doing and in what order. It is written so that Bardia can explain every part of it out loud.
Technical words are defined the first time they appear.

## What the project is

In the children's game Telephone, a sentence is whispered from one person to the next and comes
out the other end changed. This project plays that game with a photograph. The photo is passed
again and again through the systems that handle pictures online, and each pass is measured.

There are four kinds of station a photo can pass through:

1. Platform. Does what an upload to Instagram or WhatsApp does: shrinks the picture, re-saves it
   as a JPEG at the platform's quality, and strips the hidden metadata (camera, date, location).
2. Reader. An AI vision model writes a description of the picture in words.
3. Painter. An AI image model draws a new picture from that description alone.
4. Screenshot. Shows the picture on a phone screen and takes a screenshot of it.

A chain is one of my photographs plus a chosen list of stations, run round and round. Each trip
round the loop is one generation, also called one pass. The site says "pass". Generation 0 is the
original; generation 1 is what comes out after one trip; and so on for a set number of trips.

At every generation two things are measured:

- Drift: how far the picture has moved from the original, as a number.
- Survival: which facts about the picture are still there. A vision model fills in a fixed form
  for every generation (objects, number of people, visible text, setting, lighting, mood, main
  colours, camera angle, whether it still looks like a photograph). Each answer is compared with
  the answer for generation 0, so we can say which fact died first.

The platform-only chain is the baseline: it shows how much damage plain compression does before
any AI is involved.

## Why it matters

A photograph matters because it is specific: this place, this light, this person. The systems
that carry photographs now keep what is typical and drop what is specific. Telephone shows that
happening to my own photographs, one pass at a time, and names what goes first.

It is for ordinary people first. The photo you send is not the photo that arrives, and when a
machine describes or redraws your picture, the project shows what it thinks matters. Photographers
come second: it shows which parts of a picture are fragile in circulation. Tutors come third.

Two everyday cases show what this means. A photo re-sent through messaging apps is usually shrunk
and re-saved each time. A description written by a machine, such as the automatic alt text some
platforms add, has to choose what to mention, and what it leaves out is gone for anyone who only
has the description.

The module handbook covers both halves. Week 3 is about "what changes when photographs become
data: files that can be encoded, compressed, copied, analysed, transformed and circulated through
networks". That is the compression half. Week 7 is about "what happens when photographs are made
not only for human viewers but increasingly interpreted by computational systems". That is the
machine-reader half. Week 5 gives the phrase for what my claim predicts: a photograph processed
through "patterns, averages and probabilities".

## The research question

When a photograph is passed along again and again, what do the systems that carry it keep and
what do they drop?

The claim to test: they keep what is typical and drop what is specific.

Five smaller questions follow, each with the experiment that answers it. A key is an API key,
which a paid AI service needs before it will run.

1. Does plain re-uploading keep damaging a photograph, or does it settle? Re-upload, no key.
   Answered by experiment 1: it settles after the first upload.
2. What makes damage keep adding up? Screenshot and forward, no key. Answered on 17 November:
   not the screenshot itself and not a change of phone. A crop that is slightly off each time.
3. Does the place survive: does Bologna stay Bologna or become "a European street"? The place
   line-up now, with no key: a first reading on 17 November. Describe and redraw when there is a
   key.
4. What does a machine put in place of what it drops? That means what it adds that was never
   there. Describe and redraw, needs a key. The module's topic of algorithmic bias (an automated
   system treating some people or things as the norm) comes in here. On the self-portrait chain,
   who the machine turns me into is evidence of its defaults.
5. Do people keep different things from machines? Human telephone. The captions need no key. The
   redrawing does.

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

The four assessment criteria, and what in this project answers each:

- The ability to formulate a practice-led research experiment in response to the brief: the main
  question, the claim to test and the five smaller questions.
- Evidence of critical engagement with online environments through practical experiments and
  project development: each experiment copies something that happens to pictures online, and the
  dev diary records what failed and what changed.
- Application of technical strategies: the loop, its measurements, and the checks on the
  measuring tools themselves.
- Coherence in the production and presentation of the final project: the site, the log and this
  brief follow one question in the same plain words.

The marks reward the research and the log more than the website. The website must never replace
the experiments.

## Deadlines

| Date | What |
|---|---|
| 10 Nov 2026 | 1-1 tutorial. Show a first real loop on a few of my own photos. |
| 17 Nov 2026 | Second tutorial. Today. |
| 24 Nov 2026 | Supervised project development. Target, to confirm: the three experiments that need no key done, with metrics (1 to 3 in the plan below). |
| 1 Dec 2026 | 10-minute work-in-progress presentation. |
| 8 Dec 2026 | Essay tutorial. The essay is a separate assessment. |
| 5 Jan 2027, 1pm | Final submission on Blackboard: practical outcome plus the log as a PDF. |

## The photographs

All six are mine and live in `data/originals/`. The word before the first underscore is the photo
type. Results are read per photograph.

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
has already been through one platform. This is recorded in the dev diary. To show that an upload
removes the hidden camera data, I need to add originals straight from my phone, because these six
had already lost theirs. If they replace these six, the experiments are re-run.

Two more things I still need to do. `data/places.yaml` records where each photograph was taken,
copied from this table, and I need to confirm those labels. I also need to write my own
one-sentence caption for each photograph, in `data/human/captions.yaml`
(`docs/human-telephone.md` says how).

Photos that must stay private go in `data/originals/private/`. That folder is never committed
and never exported to the website.

## Where things stand (17 November 2026)

Steps 0 to 2 were done on 9 November: this brief, the re-upload experiment on all six
photographs, and the six audited bugs fixed with tests. On 17 November, with no key: the
Screenshot station, the screenshot-and-forward experiment, the place line-up,
`telephone detail-test`, and the website rebuilt as one page. Both experiments have been run on
all six photographs and saved. The numbers are in `docs/dev-diary.md` and, to say out loud, in
`docs/tutorial-17nov/summary.md`.

Found on 17 November:

- A step that is repeated exactly settles. Uploading again stops changing the picture at pass 4
  or 5. Screenshotting on one phone stops at pass 14 to 18. I had expected the screenshot loop
  to keep decaying.
- How much is lost before it settles depends on how the phone redraws the picture: 75 to 86% of
  the fine detail is left with one way of resampling (working out the new pixels when a picture
  changes size) and 39 to 53% with the other.
- A different phone every pass keeps changing the picture but levels off: 71 to 86% of the fine
  detail is left after 40 passes. A careless crop every pass keeps wearing it down: 16 to 30% is
  left, and 53 to 73% of the frame.
- The place. On the originals the true place comes first in its line-up of 12 for all six
  photographs. It stays first through 40 passes of the upload, one-phone and many-phones
  journeys. Under the careless crop Bologna stays first, but its probability falls from 0.72 to
  0.44. Under the harshest upload setting from experiment 1 the true place loses first place for
  three photographs: Bologna comes second to Padua. This is one model and one list of names,
  and the margins are thin.

Four measuring tools turned out to be wrong, and each was fixed or replaced:

- The project's SSIM measure (a score of how alike two pictures are in structure) shrinks
  pictures to 512 pixels wide before comparing, so it cannot see the loss of detail finer than
  that. `telephone detail-test` compares each pass with the same region of the original at the
  picture's own size, and follows the crop.
- The first version of that fine-detail measure counted the speckle that saving a JPEG adds. It
  now counts only the original's detail that is still in place.
- CLIP is a model that runs locally, with no key, and scores how well a picture matches a text
  or another picture. It had been built with the wrong activation function for its weights: a
  step inside the network did not match the one the model was trained with. The library only
  warned. It is fixed, a test fails if it happens again, and experiment 1 was measured again.
  The CLIP distances in `docs/tutorial-10nov/summary.md` changed, and that file now carries a
  dated correction. SSIM, LPIPS (a learned score of how different two pictures look) and file
  sizes were not affected.
- The first rule for "has it stopped changing" counted the first pass that changed nothing. A
  chain now counts as settled only when no later pass changes it.

One prediction failed and is kept as failed. The abstract reflection crop was put into the place
line-up as a control, a picture that should not be placeable. On the corrected model its true
place came first anyway. The first calibration, scored on the mis-built model, is kept in
`docs/evidence/` as a record.

On the website, Bardia confirmed on 17 November who it is for (the order above), that it keeps
its current look for now, and that it must not feel like an advert for an AI product or a wall of
text. It is now one plain-language page plus "How it works" and "About". A visitor chooses what
happens to a photograph, presses "Pass it on" and reads what is left. A "try your own photo"
step runs entirely in the visitor's browser. The older technical pages are kept under `/lab` and
are not linked from the published site. `PRODUCT.md` records the decisions. The Impeccable engine
could not run in the cloud session, so no new look was created. That is a later step on Bardia's
own machine. The published site only changes when this branch is merged into `main`.

There are still no API keys, and nothing has been spent. Anything with a Reader or Painter
station, and the survival form, waits for a key. The plan below says what runs without one.

Rules about money and keys:

- Total API spend cap for the whole project: $15 (assumed, see the end of this file). The
  software refuses a call that would go over it.
- No paid call is ever made without saying the estimated cost first.
- Keys are never pasted into chat. When one is needed, it goes in through the secure credential
  form, and from there into the environment as `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`.
- Tests and CI only ever use mock providers (fake stand-ins that cost nothing). If mock output
  ever appears in public, it is labelled "simulation".

## The plan

The experiments, in story order. The file numbers no longer run in this order, so each experiment
is called by its name, with its file in brackets. Question numbers are the ones above.

1. Re-upload (`experiments/exp01_compression.yaml`). For question 1. Done on 9 November, and
   measured again on 17 November after the CLIP fix.
2. Screenshot and forward (`experiments/exp07_screenshot_loop.yaml`). For question 2. Each pass
   shows the picture on a phone screen, takes a screenshot and uploads that. Variants: a
   re-upload control, an exact crop, an exact crop with a second way of resampling (working out
   the new pixels when a picture changes size), a different phone every pass, and a crop that is
   a few pixels off. Done on 17 November, no key.
3. The place line-up (`data/places.yaml` and the command `telephone place-test`). For question 3.
   Each photograph has a fixed line-up of 12 candidate places written as bare names, fixed before
   any score was seen, and the local CLIP model ranks them. The measurement is "the true place
   comes first, or Nth, in a line-up of 12", always quoted with its probability. It is an
   instrument for describe and redraw. On the compression chains it is the control, the baseline
   to compare against. Built and run on both experiments on 17 November, no key.
4. Describe and redraw (`experiments/exp02_caption_length.yaml`). For questions 3 and 4. The core
   loop: the Reader describes and the Painter redraws. Needs keys. The old photo-types experiment
   (`experiments/exp04_photo_types.yaml`) is folded into this one.
5. Human telephone. New, for question 5. A person writes the sentence and the Painter redraws
   from it. The captions can be collected on paper now, which needs me. The redrawing needs a
   key. It could be run live in the 1 December presentation.
6. Physical loop (`experiments/exp06_physical.yaml`). A phone photographs a screen showing the
   previous pass. No key. Needs me: only I can shoot it.

Two experiments are set aside: swapping the reader and painter models
(`experiments/exp03_system_swap.yaml`) and mixed chains (`experiments/exp05_mixed_chains.yaml`).
They serve the engineering side of the project more than the question. The files are kept, and
neither is planned for the log.

Steps still to do:

Step 3. Get a free Google AI Studio key for Gemini, with a walkthrough. Run a few
describe-and-redraw loops on Gemini only. The plan and the estimated cost come first. The free
tier may let Google use what is sent to it (see Ethics).

Step 4. Save the real results as preloaded examples, so the website and the deck always have real
content even with no keys. Done for the experiments without AI: `telephone export-site` writes
what the page shows into `web/public/data/`, and it is committed. To repeat when describe and
redraw has run.

After that:

- Two changes to the survival form when a key arrives, not built yet. Split it into specific
  facts (the named place, the exact words on a sign, the coot, me) and generic facts (setting,
  mood, colours), so that "specific dies before generic" can be tested. Record what the machine
  adds as well as what it loses.
- The log: `log/outline.md` holds 19 slides up to 17 November and builds with
  `python log/build_deck.py`. Still to come: the slides for describe and redraw, and the
  hand-labelled validation of the metrics.
- The README was brought up to date on 17 November.

## Words

| In the code | On the site |
|---|---|
| generation | pass |
| run the loop | pass it on |
| drift | how far it has moved from the original |
| survival | what is left ("still here" / "gone") |
| describe and redraw | the only loop called a "retelling" |
| variant | journey ("Upload it again", "A careless crop every time") |
| settled | it has stopped changing |

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

In a cloud session the Impeccable engine and the Superpowers plugin may not be installed. On
17 November the site was simplified under Impeccable's written rules with its current look kept,
and test-first was followed by hand.

## References

Claude wrote the notes on what each text says. "Handbook" marks the module handbook's own words.
"Claude's gloss" marks Claude's own reading, which Bardia needs to check against the text before
citing it.

From the module reading list:

- Steyerl, H. (2023) "Mean Images", *New Left Review*, 140/141,
  https://newleftreview.org/issues/ii140/articles/hito-steyerl-mean-images. Week 5 set reading.
  Handbook: Week 5 builds on Steyerl's concept of the "mean image". Claude's gloss: "mean" in the
  sense of average, which would be the "typical" in my claim.
- Salvaggio, E. (2022) "How to Read an AI Image: The Datafication of a Kiss", *Cybernetic
  Forests*, https://cyberneticforests.substack.com/p/how-to-read-an-ai-image. Week 5 set reading.
  Claude's gloss, from the title: a way to read the redrawn pictures for question 4.
- Palmer, D. (2013) "The Rhetoric of the JPEG", in Lister, M. (ed.), *The Photographic Image in
  Digital Culture*. London: Routledge. Week 2 further reading. Claude's gloss, from the title:
  about the JPEG format, which every Platform pass saves into.
- Manovich, L. (2001) *The Language of New Media*. Cambridge, MA: MIT Press, chapter "What Is New
  Media?". Week 3 key reading. Handbook: new media as "numerically represented, programmable and
  variable". A photograph stored as numbers can be re-encoded on every pass.
- Malevé, N. (2023) "Ways of Machine Seeing as a Problem of Invisual Literacy", in *The Networked
  Image in Post-Digital Culture*. London: Routledge. Module reading list. Claude's gloss, from
  the title: about how machines see pictures, which the Reader and the place line-up both do.
- Osborne, P. (2010) "Infinite Exchange: the social ontology of the photographic image",
  *Philosophy of Photography*, 1 (1), pp. 59 to 68. Week 2 key reading. Claude's gloss, from the
  title: passing a photograph along is a kind of exchange.
- Steyerl, H. (2009) "In Defense of the Poor Image", *e-flux journal*, no.10. Week 3 key
  reading. Claude's gloss: the compressed, copied, low-resolution image is the image that
  actually circulates.
- Paglen, T. (2016) "Invisible Images (Your Pictures Are Looking at You)", *The New Inquiry*,
  8 December. Week 7 set reading. Most images are now made for and read by machines.
- Crawford, K. and Paglen, T. (2019) "Excavating AI: The Politics of Images in Machine Learning
  Training Sets", https://excavating.ai/. Week 1 suggested reading. The labels machines attach to
  images are partial and loaded.

Artists and precedents:

- Pete Ashton, *I Am Sitting in Stagram* (2015). One photo reposted to Instagram 90 times, each
  repost a screenshot of the last. The closest precedent for the compression loop.
- Alvin Lucier, *I Am Sitting in a Room* (1969). A voice re-recorded in a room until only the
  room's resonance is left. The original "channel becomes the subject" piece.
- Thomas Ruff, *jpegs* (2004 onwards). Compression as a visual subject.
- Rosa Menkman, *Glitch Studies Manifesto* (2010). Compression artefacts as aesthetic.

Papers:

- Shumailov et al., *AI models collapse when trained on recursively generated data*, Nature
  (2024). Recursive generation forgets the rare details first. This predicts what should die first
  in my chains.

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
- A visitor's own photograph never leaves their browser. The "try your own photo" step runs on
  their device and nothing is uploaded or stored (decided 17 November 2026).
- People who write captions for the human telephone chain are asked whether their words can be
  shown, and are not named.
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

Decisions taken on 17 November that Bardia has not confirmed one by one. Strike or keep each:

5. The place labels in `data/places.yaml`.
6. Correcting the CLIP build, which changes the CLIP distances quoted on 10 November.
7. The "try your own photo" step.
8. Setting aside the two experiments.
9. The word "pass" for generation.
10. The careless crop as the first journey the site shows, because it is the one where a visitor
    can see something happen.
11. Keeping the older technical pages under `/lab`, and removing the live-run page, which needs
    a server.

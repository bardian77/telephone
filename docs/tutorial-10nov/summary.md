# Experiment 1, for the 10 November tutorial

Half a page to say out loud. Figures are in `figures/`: one contact sheet and one drift chart per
photograph (`contact_<photo>.jpg`, `drift_<photo>.png`). The numbers below come from
`analysis/tutorial_10nov.py`, which reads the run ledger; the full rows are in
`data/results/exp01_compression.jsonl`.

## What I did

I took my six photographs and put each one through a pretend upload twenty times in a row. One
upload shrinks the picture to the platform's maximum size, re-saves it as a JPEG at the
platform's quality, and strips the metadata. I did it four ways: like WhatsApp (1600 px, quality
60), like Instagram (1080 px, quality 72), a phone screenshot re-sent on WhatsApp, and a
deliberately harsh setting (512 px, quality 30). No AI is involved yet; this is the baseline.

After every pass I compared the result with the original using three measures. SSIM compares
pixel structure, where 1 means identical. CLIP distance compares what an image-recognition model
sees, where 0 means identical and, for scale, two of my different photographs are 0.43 apart.
LPIPS is a learned measure of perceptual difference, again 0 for identical. That is 24 chains and
504 generations, run on my laptop-class machine with nothing spent on APIs.

## What happened

Almost all the damage happens on the first upload, and then nothing more happens. The WhatsApp
and Instagram presets cut each file to between a half and a sixth of its size (the Barbican lake
goes from 487 kB to 156 kB on Instagram) while SSIM stays above 0.97 and CLIP distance moves by
0.01 to 0.03, which is 2 to 6 percent of the distance between two different photographs. The
harsh preset takes SSIM down to between 0.83 and 0.93 and CLIP distance up to between 0.06 and
0.12. From generation 1 to generation 20 the numbers do not move. Thirteen of the 24 chains end up
producing byte-for-byte identical files after 3 to 13 passes; the other eleven keep shuffling a
few dozen bytes without changing the picture.

## What surprised me

I expected gradual decay, like Pete Ashton's ninety Instagram reposts. Instead the loop gets stuck
after one pass, because re-saving a JPEG at the same size and quality gives back almost the same
JPEG. Ashton's pictures decayed because every repost was a screenshot, so the pixel grid moved a
little each time. The re-upload story turns out to be a re-sampling story.

Two smaller surprises. The vertical Bologna photo lost the most structure under every preset
(SSIM 0.83 at the harsh setting, against 0.88 to 0.93 for the others), probably because the
arcades and the small figures are fine detail that JPEG throws away first. And the 460 px abstract
crop was never resized by any preset, since it is already smaller than all of them, yet it still
lost 3 to 9 percent of its SSIM from re-encoding alone.

One thing about the starting point: generation 0 had already been through one upload before I
began. The app I used to get the photos into the project resized them to 2000 px and removed their
metadata. I have noted it and may swap in full-quality originals from my phone.

## What's next

First, a change to this experiment: add a variant that moves the pixel grid every pass, with a
small crop or a different size each time, to test whether re-sampling is what makes decay add up.
Second, the real loop: a vision model describes the photo and an image model redraws it from the
description, on Gemini's free tier, behind a spend cap. I expect CLIP distances far above 0.1
there, and the question becomes which facts about Bologna or the Barbican survive the retelling.

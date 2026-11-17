# What changed by 17 November

A page to say out loud. Figures are in `figures/`, screenshots of the site in `site/`. The numbers
come from `analysis/tutorial_17nov.py`, which reads the saved results in `data/results/`. Nothing
was spent: there is still no API key, so no AI has touched the photographs yet.

## The why

Last week my question was "what does a photograph keep and lose". It had no reason in it. Now it
does:

A photograph matters because it is specific: this place, this light, this person. The systems
that carry photographs keep what is typical and drop what is specific. I pass my own photographs
along, again and again, and name what goes first.

That comes straight from the module. Week 5 talks about visual culture "processed through
patterns, averages and probabilities". My claim is what that would mean for one photograph.

## What I did

Last week's result was that re-uploading a photo does almost nothing after the first upload. I
guessed that screenshots were what wore Pete Ashton's picture down, because a screenshot redraws
the picture on a phone screen. So I built that step and ran five versions of it, 40 passes each,
on all six photographs: 30 chains and 1230 saved files.

1. Upload it again. The control, the same as last week.
2. Screenshot it on one phone, then upload.
3. The same, with the phone redrawing the picture in a cruder way.
4. A different phone every pass, as when a picture is forwarded from person to person.
5. A careless crop every pass: each screenshot is cropped a few pixels off.

I also built a first test of whether the place survives. For each photograph I wrote a list of 12
place names that includes the true one, before measuring anything. A vision model (CLIP, which
runs on my own machine) scores how well each name matches the picture. I record where the true
name comes in the list.

## What happened

A step that is repeated exactly settles. Uploading again stopped changing the picture at pass 4
or 5. Screenshotting on one phone stopped at pass 14 to 18. So I was wrong a second time:
screenshots on their own do not keep wearing a picture down either.

How much is lost before it settles depends on how the phone redraws the picture. After 40 passes
the plain upload had 91 to 95% of the original's fine detail left. One phone left 75 to 86%. The
cruder way of redrawing left 39 to 53%. I do not know how a real phone does it, which is why I
ran both.

A different phone every pass kept changing the picture, but more and more slowly. After 40 passes
it had 71 to 86% of its fine detail left, only 1 to 5 points less than on one phone. I expected
it to run away, and it did not.

The careless crop is what keeps wearing a picture down. After 40 passes 16 to 30% of the fine
detail was left, and it was still falling. 53 to 73% of the frame was left. A crop that is
slightly off moves the picture against the screen's grid of pixels, so every pass blurs it a
little more, and it cuts the edges away.

These numbers are for five photographs. The sixth is a 460 pixel crop, smaller than the app's
size. The app enlarges it, so there is nothing fair to compare it with, and I report it apart.

## The place

On the originals, the true place came first in its list of 12 for all six photographs. The model
gave it 99% of its confidence for the Barbican lake and 98% for the Seddon House sign, 72% for
Bologna, 60% for the larches and 30% for the self-portrait.

Through 40 passes of uploading, of one phone and of a different phone each time, the true place
stayed first for every photograph at every pass. The careless crop is different. Bologna stayed
first, but its share fell from 72% to 44%. The self-portrait lost first place on 22 of the 40
passes.

The clearest sign came from last week's harshest upload setting (512 pixels, quality 30). One
such upload narrowed the true place's lead over the next name for all six photographs, and for
three the lead was lost. Bologna came second to Padua. In the self-portrait the Dolomites fell to
fourth, and on its ladder from specific to general the best match moved from "the Alps" to "the
mountains". That is a small case of my claim with no AI involved: the specific name gave way to
the next-door one, or to the general one.

I am careful with this. It is one model and one list of names. The leads are thin: thousandths
on the model's own scale. Coming first in a list does not mean a machine knows the place.

## What went wrong, and what I changed

These are the part of the week I would most like to talk about.

- My similarity score could not see the damage. It compares copies shrunk to 512 pixels wide.
  After 40 passes it put the one-phone screenshot within 0.002 of the plain upload for all five
  photographs, when one had 75 to 86% of its fine detail left and the other 91 to 95%. I built a
  comparison that works at the picture's own size.
- The first version of that comparison was wrong too. It counted all the pixel-to-pixel
  variation in a picture. A picture that had been saved twice scored 1.83, "183% of the detail",
  while a standard score said it had got worse (SSIM 0.86). Saving adds speckle, and the measure
  was counting it. It now counts only the original's detail that is still in the same place
  (0.98 for that picture), and keeps the total beside it (1.42).
- For the careless crop, my first numbers measured the cropping and not the damage. The
  comparison now follows the crop. I checked that it lines up: across all 1230 files the best
  alignment was the one it predicted.
- The vision model had been built with the wrong setting for its weights. The software only
  warned. Every CLIP number I showed last week came from that. I measured experiment 1 again:
  all 504 files came out byte for byte the same, and the CLIP distances moved a little. The
  correction is at the top of last week's summary.
- A prediction failed. I put the reflection crop in as a control, a picture the model should not
  be able to place. On the corrected model its true place came first, with 60%. I have kept that
  as a failed prediction. I do not know whether the crop holds more of the place than I thought,
  or the score responds to something that is not the place.
- My test for "has it stopped changing" fired too early. One of the phones in the fourth journey
  is the same size as the app, so that pass changes nothing, and the next phone changes the
  picture again. A chain now counts as settled only when no later pass changes it.

## The website

It is one page now, in plain words. A visitor sees one photograph, chooses what happens to it,
presses "Pass it on" and reads what is left: the size, the fine detail, the frame, the place,
whether it is still changing. A close-up shows the same spot at every pass. They can try it with
their own photo, which never leaves their browser. The measurements and what they cannot show
are on a second page.

## What I need to do myself

- Confirm the six place labels in `data/places.yaml`.
- Write my own one-sentence caption for each photograph (`data/human/captions.yaml`).
- Get the Gemini key, so the describe-and-redraw loop can run. That is where the claim is really
  tested.
- Shoot the physical loop (`docs/physical-loop.md`) and collect captions from classmates
  (`docs/human-telephone.md`).

## Questions for the tutorial

1. Is "keeps the typical, drops the specific" a strong enough reason, and is the place test a
   fair way to make it measurable?
2. The half without AI has grown. How much of the log should it take, against the
   describe-and-redraw loop that has not run yet?
3. The careless crop is my model of a person cropping a screenshot by hand. Should I do that by
   hand on my own phone as well, so the model can be checked against the real thing?
4. Would running the human telephone chain with the class on 1 December count as part of the
   practical outcome?

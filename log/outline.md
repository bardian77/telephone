# Research and Experimentation Log: outline

5IMAG022W The Networked Photograph · Experimentation Portfolio · Bardia Nasab

This file is the log. `python log/build_deck.py` turns it into slides (see the top of that file
for the two marks, `[WIDE]` and `[RESULTS]`). Every '## N.' heading is a slide. Every number here
comes from a saved results file in `data/results/` and is quoted in `docs/dev-diary.md` or
`docs/tutorial-17nov/summary.md`. The brief asks for 10 to 20 slides.

---

## 1. Telephone
- **A photograph matters because it is specific: this place, this light, this person.** The systems that carry photographs keep what is typical and drop what is specific.
- I pass my own photographs along, again and again, the way the children's game passes a sentence along, and I measure what is left after every pass.
- This log covers the half of the project that needs no AI: uploads and screenshots. It already changed what I thought I knew.
- Bardia Nasab · 5IMAG022W The Networked Photograph · Experimentation Portfolio. Figure: `docs/tutorial-17nov/site/home-desktop-original.jpg`

## 2. The question
- When a photograph is passed along again and again, what do the systems that carry it keep, and what do they drop?
- The claim I am testing: they keep what is typical and drop what is specific.
- Five smaller questions. 1: does plain re-uploading keep damaging a photograph, or does it settle? 2: what makes damage keep adding up? 3: does the place survive? 4: what does a machine put in place of what it drops? 5: do people keep different things from machines?
- So far, with no paid service, I have answers to 1 and 2 and a first reading on 3. Questions 4 and 5 need an API key I do not have yet.

## 3. Context: pass it along until the channel shows
- Pete Ashton, *I Am Sitting in Stagram* (2015): one photograph reposted to Instagram 90 times, each repost a screenshot of the last.
- Alvin Lucier, *I Am Sitting in a Room* (1969): a voice re-recorded in a room until only the room's resonance is left.
- Why they matter here: both make the channel the subject. My first two experiments repeat Ashton's method under conditions I control, and it does not behave the way I assumed it would.

## 4. Context: the typical and the specific
- Hito Steyerl, "Mean Images" (2023), the Week 5 set reading. The module handbook describes visual culture "processed through patterns, averages and probabilities". My claim is what that would mean for one photograph: the average stays and the particular goes.
- Shumailov and others, "AI models collapse when trained on recursively generated data", *Nature* (2024): when a generating system is fed its own output, the rare details go first.
- Why they matter here: together they predict what should disappear first when a machine describes my photograph and another machine redraws it. The named place, the words on a sign, me.

## 5. Context: the picture as a file, the picture as something a machine reads
- Week 3, "Image as Data": what changes when photographs become "files that can be encoded, compressed, copied, analysed, transformed and circulated through networks". Hito Steyerl, "In Defense of the Poor Image" (2009). Daniel Palmer, "The Rhetoric of the JPEG" (2013). Thomas Ruff, *jpegs*. Rosa Menkman, *Glitch Studies Manifesto*.
- Week 7, "Images for Machines": Trevor Paglen, "Invisible Images (Your Pictures Are Looking at You)" (2016). Most images are now made for and read by machines.
- Why they matter here: the first half of my project treats the photograph as a file. The second half asks a machine where my photographs were taken.

## 6. The first idea, and how it changed
- Early November: a photograph goes round a loop of upload, machine description and machine redrawing, and I measure how far it drifts.
- 9 November: a first version did all of that at once, with six experiments and a website of eight pages. I could not explain it, so I cut it back. Experiments and this log first, the website last.
- 17 November: the question got its reason. It went from "what does a photograph keep and lose" to "do these systems keep the typical and drop the specific".
- I have no API keys yet, so everything in this log is the half without AI. It held more than I expected.

## 7. Method
- One pass is one trip round a loop. An upload shrinks the picture to the app's size, saves it as a JPEG and removes the hidden camera data. A screenshot shows it on a phone screen and captures the screen.
- Six photographs of mine. Every pass is saved and measured: the file size, the fine detail at full size, how much of the frame is left, where the true place comes in a list of 12 place names, and whether the pass changed anything.
- I wrote the 12 names for each photograph before scoring anything, and a test fails if the lists change.
- Nothing here cost money, and all of it can be run again from the repository. Running experiment 1 again a week later gave the same 504 files, byte for byte. Figure: `docs/tutorial-17nov/figures/six_photographs.jpg`

## 8. Experiment 1: upload it again, 20 times
- Four upload settings, six photographs, 20 passes each: 24 chains.
- I expected a slow slide, like Ashton's 90 reposts. Almost all of the change happens on the first upload. After that the loop hands back the picture it was given.
- Change of direction: re-uploading is not what wore Ashton's picture down. His reposts were screenshots, so the picture was redrawn every time. Figure: `docs/tutorial-10nov/figures/contact_street_barbican_lake_01.jpg`

## 9. [WIDE] Experiment 2: screenshot it, then upload, 40 times
- On one phone the loop still settles, later than the plain upload. On a different phone every pass, or with a careless crop, it had not settled after 40 passes. Figure: `docs/tutorial-17nov/figures/settled_at.png`
- Five journeys, six photographs, 40 passes: 30 chains, 1230 files. A journey counts as settled from the pass after which nothing changes again.

## 10. [WIDE] A failed instrument: my similarity score could not see the damage
- After 40 passes my first score put the one-phone screenshot within 0.002 of the plain upload. Measured at full size, one had 75 to 86% of its fine detail left and the other 91 to 95%. Figure: `docs/tutorial-17nov/figures/two_measures.png`
- The first score compares copies shrunk to 512 pixels wide, so it cannot see detail finer than that. I built a comparison that works at the picture's own size.

## 11. [WIDE] Fine detail, pass by pass
- A step repeated exactly settles. A different phone every pass levels off. The careless crop keeps wearing the picture down: 16 to 30% of its fine detail is left after 40 passes, and still falling. Figure: `docs/tutorial-17nov/figures/detail_by_journey.png`
- How the phone redraws the picture matters more than how many times it does it: 75 to 86% is left with one way of resampling, 39 to 53% with the other. Five photographs; the 460 px crop is reported apart.

## 12. [WIDE] The same spot at every pass
- The small sign with its lettering is the kind of specific detail my claim is about. After 40 uploads it is still there. Under the careless crop it has left the frame by pass 20. Figure: `docs/tutorial-17nov/figures/closeup_text_barbican_seddon_house_01.jpg`
- Each cell is cut from the saved file with no processing. Rows are the five journeys; columns are the original and passes 1, 5, 10, 20 and 40.

## 13. A second failed instrument, and a prediction that failed
- The vision model I use for the place test had been built with the wrong setting for its weights, and the software only warned. Every number from it was measured again.
- On the corrected model the true place comes first of 12 for all six photographs. Open circles are before the fix, filled circles after.
- The prediction that failed: I put the reflection crop in as a control, a picture the model should not be able to place. It placed it, with 60%. I kept that as a failed prediction and did not change the list.
- Experiment 1, run again, gave the same 504 files. Only the numbers that come from the model moved. Figure: `docs/tutorial-17nov/figures/place_calibration.png`

## 14. [WIDE] Does the place survive?
- Through 40 uploads, on one phone or on many, the true place stays first for every photograph. Under the careless crop Bologna stays first, but its share falls from 72% to 44%. Figure: `docs/tutorial-17nov/figures/place_over_passes.png`
- One harsh upload (512 pixels, quality 30) narrows the true place's lead for all six photographs, and Bologna comes second to Padua. This is one model, one list of 12 names, and thin margins.

## 15. What went wrong, and what I changed
- I expected re-uploading to wear a picture down. It settles at once. I expected screenshots to do it. They settle too. I expected a different phone each pass to do it. It levels off. What does it is a crop that is slightly off.
- Two of my measures were wrong: the 512 pixel score that saw nothing, and a first fine-detail measure that gave 183% to a picture that had got worse.
- The model was built wrongly, and my test for "has it stopped changing" fired too early.
- My six originals had lost their hidden camera data before the project began. The app I used to move them had removed it.
- The first version of the project was too technical to explain, and its website had eight pages.
- Each of these is in `docs/dev-diary.md`, with what I changed.

## 16. [RESULTS] Next: a machine describes it, and a machine redraws it
- This is the loop the project is named after. It needs an API key, which I do not have yet.
- The survival form will be split into specific facts (the named place, the words on a sign, the coot, me) and generic ones (setting, mood, colours), to test whether the specific ones go first.
- I will record what the machine adds as well as what it drops. On my self-portrait, who it turns me into is evidence of its defaults.
- Two more loops need me and not a key: classmates writing the description in place of the machine, and a phone photographing a screen. Figure: `data/figures/exp02_caption_length/survival_fraction_by_variant.png`

## 17. The outcome so far: the website
- One page in plain words. Choose what happens to a photograph, press "Pass it on", and read what is left: the size, the fine detail, the frame, the place, and whether it is still changing.
- A close-up shows the same spot at every pass. Every picture is the saved file itself, never compressed again for the web.
- "Try it with your own photo" does the passes inside the visitor's browser. Nothing is uploaded.
- How each thing is measured, and what the measurement cannot show, is on a second page. Figure: `docs/tutorial-17nov/site/home-desktop-pass40.jpg`

## 18. Reflection so far
- What I found: copying a picture the same way again and again does little after the first time. The damage comes from small human things, such as a crop that is slightly off, and from how each device redraws the picture.
- On my claim: with no AI involved, the specific already gives way first under heavy compression. Bologna becomes a nearby Italian city in a machine's list. That is one model with thin margins, and the real test is still to come.
- What surprised me most was how often the measuring tool was the thing that was wrong.
- Limits: six photographs, one model, and my own stand-ins for an app and a phone. Ethics: only my own photographs; a visitor's photo never leaves their browser; nothing has been sent to an AI service yet.

## 19. References
- Ashton, P. (2015) *I Am Sitting in Stagram*. Lucier, A. (1969) *I Am Sitting in a Room*. Ruff, T. (2004 onwards) *jpegs*. Menkman, R. (2010) *Glitch Studies Manifesto*.
- Steyerl, H. (2009) "In Defense of the Poor Image", *e-flux journal*, no. 10. Steyerl, H. (2023) "Mean Images", *New Left Review*, 140/141. Paglen, T. (2016) "Invisible Images (Your Pictures Are Looking at You)", *The New Inquiry*, 8 December. Palmer, D. (2013) "The Rhetoric of the JPEG", in Lister, M. (ed.), *The Photographic Image in Digital Culture*. London: Routledge.
- Shumailov, I. et al. (2024) "AI models collapse when trained on recursively generated data", *Nature*. Radford, A. et al. (2021), CLIP. Wang, Z. et al. (2004), SSIM. Zhang, R. et al. (2018), LPIPS.
- The code, the data and every result: github.com/bardian77/telephone

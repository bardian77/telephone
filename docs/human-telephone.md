# Human telephone: people as the reader

In the describe-and-redraw loop a machine looks at the picture and writes a description. Here a
person does that job. The point is to compare what people keep with what a machine keeps.

The question this answers: do people name the specific place, the words on the sign, the bird or
the person, where a machine gives a generic scene? That is the question, not the result. Nobody
knows yet.

There are two versions. Version A needs no key and can be done today. Version B is the real
telephone game and needs the painter key.

## What you need

- The six photographs, lettered A to F (the letters are listed in `data/human/captions.yaml`).
- A screen or printouts to show them on.
- Printed copies of `docs/human-telephone-sheet.md`, one per reader, and pens.
- A phone timer.
- 6 to 10 readers. Classmates or friends are fine.

## Say this first (consent)

Read it out before anyone writes:

> I am doing a student project about what gets kept when a photograph is described and redrawn.
> I will show you a picture for 30 seconds and ask you to describe it in one sentence. Your
> sentence may be shown in my project and on its website, without your name. I am not collecting
> anything else about you. You can say no, and you can ask me later to take your sentence out.

Each reader ticks the consent box on their sheet. No tick, no use: keep the sheet out of the data.

## Version A: many readers, one picture

Use this to see what people notice first. It needs no key.

1. Pick two or three photographs. The Bologna street (A) and the Seddon House sign (C) are a good
   pair: one tests whether people name the place, the other whether they copy the small text.
2. Show the first photograph to everyone for 30 seconds. No talking.
3. Hide it. Each reader writes one sentence that describes it for someone who will have to redraw
   it from that sentence alone. Give them one minute.
4. Repeat for the next photograph.
5. Collect the sheets.

Do not say where the photographs were taken, and do not say what the project hopes to find. If a
reader asks "should I say where it is?", answer "write whatever you would need to redraw it".
Anything more would lead them.

## Version B: the chain

This is the telephone game proper. It needs the painter key, because the painter model redraws
the picture between readers.

1. Reader 1 sees the original for 30 seconds and writes one sentence.
2. Type the sentence in and let the painter redraw the picture from it.
3. Reader 2 sees only the redrawn picture, for 30 seconds, and writes one sentence.
4. Carry on down the line. Each reader sees only the picture made from the sentence before theirs.

Readers must not see the original (apart from reader 1), each other's sentences, or earlier
pictures. To compare fairly with the machine reader, run the machine chain on the same photograph
with the same painter and the same number of passes.

How to feed a typed sentence to the painter is not built yet. It gets built when the key arrives.

## What to write down

For every sentence, type one entry into `data/human/captions.yaml`:

- which photograph (the file name without `.jpg`)
- which version (`many_readers` or `chain`)
- the position in the chain (for version A, any running number)
- how many seconds the picture was shown
- the sentence, exactly as written, spelling mistakes included
- whether the consent box was ticked
- the date

No names go in that file.

## Evidence for the log

- Photograph the handwritten sheets laid out together, before you type anything in.
- Photograph the room set-up once (the screen, the sheets, no faces).
- Keep the paper sheets until the module is marked.

## Inside the 1 December presentation (10 minutes)

Version A fits in three minutes with the class as readers.

1. Hand the sheets out as people sit down.
2. Read the consent words (30 seconds).
3. Show one photograph for 30 seconds, then one minute to write.
4. Collect the sheets and carry on presenting.
5. If there is time at the end, read three sentences out next to the machine's sentence for the
   same photograph. That only works once the machine reader has run, so have its sentence ready
   or skip this step.

## My own captions

Separately from the readers, write your own one-sentence caption for each of the six photographs
in the `author_captions` section of `data/human/captions.yaml`. You were there, so your caption
can hold things that are not in the pixels. Nothing else in the project is allowed to fill those
in for you.

# The physical loop: a phone photographs a screen

Every other loop in this project stays inside a computer. In this one the picture leaves it: you
show a pass on a screen, photograph the screen with your phone, and that photograph becomes the
next pass. It needs no key. Only you can shoot it.

The experiment is `experiments/exp06_physical.yaml`. It runs 10 passes.

## Before you shoot: location data

A phone photograph carries hidden data: the date, the camera, and often where it was taken. These
frames are shot wherever you are sitting, and this repository is public. **Turn off location
tagging in your camera app before you start**, or the frames will publish where you were. If you
forget, remove the location before you add the files (on a phone: Share, Options, turn off
"Location").

## Which photographs

Two or three is enough, because each one is ten photographs by hand. A good pair:

- `street_bologna_portici_01`: tests whether the place survives.
- `text_barbican_seddon_house_01`: tests whether small text survives.

The choice is yours.

## How to shoot one photograph's chain

1. Use a dim room. Fix the screen brightness and leave it alone for all ten passes.
2. Open the original full screen. Nothing else on the screen: no menus, no window frame.
3. Hold the phone square to the screen, so the picture fills the frame without tilting. Keep the
   same distance every time. A stack of books to rest the phone on helps. No flash.
4. Take the photograph. This is pass 1.
5. Move it to the computer **without sending it through a chat app**, which would compress it. A
   cable, AirDrop or a cloud drive keeps the file as it is. Save it as a JPEG.
6. Name it `01.jpg` and put it in `data/physical/<photograph name>/`, for example
   `data/physical/street_bologna_portici_01/01.jpg`.
7. Open `01.jpg` full screen and photograph the screen again. That is pass 2: `02.jpg`.
8. Carry on to `10.jpg`. Each pass is a photograph of the screen showing the pass before it.

The files are read in name order, so keep the two-digit numbers: `01.jpg`, `02.jpg`, up to
`10.jpg`.

Write the pass number on a sticky note and keep it in view next to the screen (outside the frame)
so you do not lose count.

## Things that will go wrong, and are worth keeping

- Moiré: wavy bands where the screen's pixel grid meets the camera's.
- Reflections of the room, or of you.
- The colours shifting, usually towards blue or green.
- The frame creeping: each pass a little smaller or more tilted than the last.

Do not fix these. They are what the camera adds, which is the point of the experiment. Note them
in the dev diary.

## Run it

Check what the project can see:

```bash
telephone doctor
```

Run one photograph's chain. No key is needed. The survival form is switched off with
`--no-extract`, as for experiment 1, because it needs a key:

```bash
telephone run-experiment exp06 --physical-root data/physical --no-extract --image data/originals/street_bologna_portici_01.jpg
```

If a frame is missing the run stops and says which one. Add it and run the same command again; it
carries on from where it stopped.

Then measure the place line-up on it and save the results:

```bash
telephone place-test exp06_physical
```

```bash
telephone save-results exp06_physical
```

## For the log

Photograph the set-up itself once: the screen, the phone on its stack of books, the sticky note.
That picture is evidence of the method and belongs on a slide.

## Originals with their camera data

The six photographs in `data/originals/` had already lost their hidden camera data before the
project started, because the app used to bring them in removed it. To show that an upload removes
that data, the project needs originals that still have it.

1. Export two or three originals straight from your phone, by cable, AirDrop or a cloud drive.
   Not through a chat app.
2. Check they still carry the data: open the file's information panel and look for the camera
   and the date.
3. Decide about location before you commit anything. A file with location data in a public
   repository publishes where it was taken. Either remove the location and keep the date and
   camera, or put the file in `data/originals/private/`, which is never committed and never
   published. A private file can still be measured, but its pictures cannot go on the website.
4. Name the files the same way as the others (`street_...`, `landscape_...`) and add them.

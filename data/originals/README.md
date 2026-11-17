# Originals

Put your own photographs here. Only images you took or hold clear rights to.

Naming: `<type>_<slug>.jpg` where type is one of
`portrait`, `street`, `landscape`, `text`, `abstract`. Example: `street_brick_lane_01.jpg`.
The type prefix is what experiment 4 (photo types) groups by.

Photos in this folder are committed to the public repository, so cloud sessions keep them, and
every experiment picks them up automatically.

Consent: do not add images of identifiable people unless they have agreed to the image being
processed by third-party AI services and possibly published on the project website.

Photos that must stay private go in `private/`. That folder is never committed, experiments do
not pick it up (pass a file with `--image` to process one), and nothing in it is ever exported to
the website or served by the API.

## Two files that describe these photographs

- `data/places.yaml` records where each photograph was taken. The places were copied from the
  table in `docs/BRIEF.md`. Confirm each one before the place results are quoted.
- `data/human/captions.yaml` has a place for your own one-sentence caption for each photograph
  (`author_captions`). They are empty until you write them.

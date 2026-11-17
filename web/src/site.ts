// What the one-page site reads: web/public/data/site.json, written by `telephone export-site`.
// The types mirror telephone/site.py. The words a visitor reads live here, not in the export.

export type PassDetail = {
  ssim_native: number | null
  detail_kept: number | null
  detail_energy: number | null
  frame_kept: number | null
  box: [number, number, number, number] | null
}

export type PassPlace = { rank: number; prob: number; top: string; place: string; lineup_size: number }

export type SitePass = {
  pass: number
  img: string
  width: number | null
  height: number | null
  bytes: number | null
  reencoded: boolean
  detail: PassDetail | null
  place: PassPlace | null
}

export type Journey = {
  chain_id: string
  generations: number
  settled_at: number | null
  passes: SitePass[]
  series: Record<string, Array<number | null>>
}

export type SitePhoto = {
  stem: string
  type: string
  width: number
  height: number
  thumb: string
  journeys: Record<string, Journey>
}

export type Site = {
  generated_at: string
  experiment: string
  passes: number[]
  photos: SitePhoto[]
  made_with: Record<string, string>
}

const BASE = import.meta.env.BASE_URL.replace(/\/?$/, '/')
export const dataUrl = (rel: string) => `${BASE}data/${rel}`

/** The export, or null when it has not been written yet. */
export async function loadSite(): Promise<Site | null> {
  try {
    const r = await fetch(dataUrl('site.json'))
    // dev and preview servers answer a missing file with index.html; only accept real JSON
    if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) return null
    return (await r.json()) as Site
  } catch {
    return null
  }
}

// The six photographs, in the order the page offers them. The descriptions are my own, from the
// table in docs/BRIEF.md.
// `focus` is where the close-up looks first: a point on the original, as fractions of its width
// and height. For the Bologna street it is the building, not the people walking past.
export const PHOTOS: Array<{ stem: string; name: string; alt: string; focus: [number, number] }> = [
  {
    stem: 'street_bologna_portici_01',
    focus: [0.78, 0.52],
    name: 'Bologna, the porticoes',
    alt: 'The porticoes of Bologna at sunset: warm terracotta arches and a few small figures.',
  },
  {
    stem: 'street_barbican_lake_01',
    focus: [0.56, 0.76],
    name: 'The Barbican lake',
    alt: 'The lake at the Barbican in London: concrete columns, reflections, a fountain and a coot.',
  },
  {
    stem: 'text_barbican_seddon_house_01',
    focus: [0.07, 0.955],
    name: 'Seddon House, the Barbican',
    alt: 'The Barbican from a low angle on an overcast day, with small signs that read Seddon House and No Cycling, No Skateboarding.',
  },
  {
    stem: 'landscape_dolomites_larches_01',
    focus: [0.3, 0.5],
    name: 'Larches in the Dolomites',
    alt: 'The Dolomites: golden larches under a blue sky, a sun flare and a small car.',
  },
  {
    stem: 'portrait_dolomites_self_01',
    focus: [0.555, 0.62],
    name: 'Me, in the Dolomites',
    alt: 'Me standing with a car in the Dolomites, taken with a very wide lens so the horizon curves.',
  },
  {
    stem: 'abstract_barbican_reflection_01',
    focus: [0.5, 0.5],
    name: 'A reflection at the Barbican',
    alt: 'A concrete column reflected in rippled water, cropped from the photograph of the Barbican lake.',
  },
]

// The journeys a photograph can take, keyed by the experiment's variant names.
export const JOURNEYS: Array<{ id: string; label: string; says: string }> = [
  {
    id: 'reupload',
    label: 'Upload it again',
    says: 'Each pass uploads the picture to a photo app. The app shrinks it and saves it again.',
  },
  {
    id: 'screenshot',
    label: 'Screenshot it, then upload',
    says: 'Each pass shows the picture on a phone, takes a screenshot and uploads that.',
  },
  {
    id: 'screenshot_many_phones',
    label: 'A different phone every time',
    says: 'The same, but every pass happens on a phone of a different size, as when a picture is forwarded from person to person.',
  },
  {
    id: 'screenshot_loose_crop',
    label: 'A careless crop every time',
    says: 'Each pass shows the picture on a phone, takes a screenshot, crops it a few pixels off and uploads that.',
  },
]

const whole = new Intl.NumberFormat('en', { maximumFractionDigits: 0 })
const oneDecimal = new Intl.NumberFormat('en', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const asPercent = new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 0 })

/** A file size in words. The space before the unit does not break across lines. */
export const kb = (bytes: number | null | undefined) =>
  bytes == null ? null : bytes >= 1_000_000 ? `${oneDecimal.format(bytes / 1_000_000)}\u00a0MB` : `${whole.format(bytes / 1000)}\u00a0kB`

export const percent = (v: number | null | undefined) => (v == null ? null : asPercent.format(v))

/** "Bologna, Italy" -> "Bologna"; "the Dolomites, Italy" -> "the Dolomites". */
export const shortPlace = (place: string) => place.split(',')[0]

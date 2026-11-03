// Types mirror telephone/export.py. Data is static JSON produced by `telephone export`.

export type Metrics = {
  clip_dist_to_g0: number | null
  clip_dist_to_prev: number | null
  hist_dist_to_g0: number | null
  hist_dist_to_prev: number | null
  ssim_to_g0: number | null
  ssim_to_prev: number | null
  lpips_to_g0: number | null
  ocr_chars: number | null
  ocr_words: number | null
  face_count: number | null
  width: number | null
  height: number | null
  file_bytes: number | null
}

export type Attributes = {
  objects: string[]
  people_count: number
  visible_text: string[]
  setting: string
  lighting: string
  mood: string
  dominant_colors: string[]
  camera_angle: string
  is_photograph: boolean
}

export type FieldSurvival = { alive: boolean; score: number; g0: unknown; now: unknown }
export type Survival = { fields: Record<string, FieldSurvival>; alive_count: number; total: number }

export type StationView = {
  kind: string
  provider: string | null
  model: string | null
  model_version: string | null
  params: Record<string, unknown>
  seed: number | null
  cached: boolean
  error: string | null
  latency_ms: number
  cost_usd: number
  list_price_usd: number
  tokens: { input: number; output: number }
}

export type Generation = {
  generation: number
  thumb: string | null
  full: string | null
  caption: string | null
  metrics: Metrics
  attributes: Attributes | null
  survival: Survival | null
  stations: StationView[]
  cost_usd: number
  list_price_usd: number
  latency_ms: number
  error: string | null
  created_at: string
}

export type Chain = {
  key: string
  chain_id: string
  experiment_id: string
  variant: string
  image: string
  type: string
  repeat: number
  seed: number
  station_sequence: string
  stations: Array<{ kind: string; provider?: string; model?: string; params?: Record<string, unknown> }> | null
  generations: Generation[]
  first_failure: Record<string, number | null>
  cost_usd: number
  list_price_usd: number
  errors: Array<{ generation: number; error: string }>
  last_generation: number
}

export type ChainSummary = {
  key: string
  chain_id: string
  experiment_id: string
  variant: string
  image: string
  type: string
  repeat: number
  station_sequence: string
  generations: number
  last_generation: number
  thumb0: string | null
  thumb_last: string | null
  final_clip: number | null
  final_hist: number | null
  final_survival: number | null
  cost_usd: number
  errors: number
}

export type CurvePoint = { generation: number; mean: number; std: number }
export type GroupSummary = {
  chains: number
  curves: Record<string, CurvePoint[]>
  first_failure_median: Record<string, number | null>
  errors: Array<{ chain_id: string; generation: number; error: string }>
  cost_usd: number
  list_price_usd: number
}

export type Experiment = {
  id: string
  title: string
  description?: string
  question?: string
  generations?: number
  repeats?: number
  variants: Array<{ name: string; stations: Array<{ kind: string; provider?: string; model?: string; params?: Record<string, unknown> }>; notes?: string | null }>
  extractor?: { provider?: string; model?: string } | null
  references?: string[]
  chains: ChainSummary[]
  summary: { variants: Record<string, GroupSummary>; types: Record<string, GroupSummary> }
  cost_usd: number
}

export type Index = {
  generated_at: string
  experiments: Experiment[]
  totals: { chains: number; generations: number; paid_usd: number; list_price_usd: number }
  images: string[]
  types: string[]
}

const BASE = import.meta.env.BASE_URL.replace(/\/?$/, '/')
let dataRoot: string | null = null

async function tryFetch(url: string): Promise<Response | null> {
  try {
    const r = await fetch(url)
    // dev/preview servers answer missing files with index.html; only accept real JSON
    const ct = r.headers.get('content-type') ?? ''
    return r.ok && ct.includes('json') ? r : null
  } catch {
    return null
  }
}

/** Real export at data/, else the committed sample at data/sample/. */
export async function loadIndex(): Promise<{ index: Index; sample: boolean }> {
  for (const [root, sample] of [[`${BASE}data/`, false], [`${BASE}data/sample/`, true]] as const) {
    const r = await tryFetch(`${root}index.json`)
    if (r) {
      dataRoot = root
      return { index: (await r.json()) as Index, sample }
    }
  }
  throw new Error('No data found. Run `telephone export` (or check web/public/data/sample).')
}

export async function loadChain(key: string): Promise<Chain> {
  if (!dataRoot) await loadIndex()
  const r = await tryFetch(`${dataRoot}chains/${key}.json`)
  if (!r) throw new Error(`Chain ${key} not found`)
  return (await r.json()) as Chain
}

export function assetUrl(rel: string | null | undefined): string | undefined {
  if (!rel) return undefined
  return `${dataRoot ?? `${BASE}data/`}${rel}`
}

export const FIELD_LABELS: Record<string, string> = {
  objects: 'objects',
  people_count: 'people count',
  visible_text: 'visible text',
  setting: 'setting',
  lighting: 'lighting',
  mood: 'mood',
  dominant_colors: 'dominant colours',
  camera_angle: 'camera angle',
  is_photograph: 'reads as a photograph',
}

export const fmt = (v: number | null | undefined, d = 2) => (v == null ? '–' : v.toFixed(d))
export const pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(v * 100)}%`)
export const usd = (v: number | null | undefined) => (v == null ? '–' : v < 0.01 && v > 0 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`)
export const showValue = (v: unknown): string => (Array.isArray(v) ? (v.length ? v.join(', ') : '(none)') : v == null ? '–' : String(v))

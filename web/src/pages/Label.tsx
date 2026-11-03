import { useEffect, useMemo, useState } from 'react'
import { assetUrl, FIELD_LABELS, loadChain, type Chain, type Index } from '../data'

type LabelRow = {
  key: string; generation: number; similarity: number; fields: Record<string, boolean>; ts: string
  clip: number | null; hist: number | null; ssim: number | null; auto: Record<string, boolean> | null
}
const STORE = 'telephone.labels.v1'
const FIELDS = Object.keys(FIELD_LABELS)

function seededPairs(index: Index, n: number, seed: number): Array<{ key: string; generation: number }> {
  const chains = index.experiments.flatMap((e) => e.chains).filter((c) => c.last_generation >= 1)
  let s = seed
  const rnd = () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296 }
  const out: Array<{ key: string; generation: number }> = []
  const seen = new Set<string>()
  let guard = 0
  while (out.length < Math.min(n, chains.length * 3) && guard++ < 10000) {
    const c = chains[Math.floor(rnd() * chains.length)]
    const g = 1 + Math.floor(rnd() * c.last_generation)
    const id = `${c.key}:${g}`
    if (!seen.has(id)) { seen.add(id); out.push({ key: c.key, generation: g }) }
  }
  return out
}

export default function Label({ index }: { index: Index }) {
  const [labels, setLabels] = useState<LabelRow[]>(() => { try { return JSON.parse(localStorage.getItem(STORE) ?? '[]') } catch { return [] } })
  const pairs = useMemo(() => seededPairs(index, 60, 42), [index])
  const done = new Set(labels.map((l) => `${l.key}:${l.generation}`))
  const next = pairs.find((p) => !done.has(`${p.key}:${p.generation}`))
  const [chain, setChain] = useState<Chain | null>(null)
  const [sim, setSim] = useState<number | null>(null)
  const [fields, setFields] = useState<Record<string, boolean>>({})
  useEffect(() => { setChain(null); setSim(null); setFields({}); if (next) loadChain(next.key).then(setChain) }, [next?.key, next?.generation])
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify(labels)) } catch { /* private window */ } }, [labels])

  const g0 = chain?.generations.find((g) => g.generation === 0)
  const gn = chain?.generations.find((g) => g.generation === next?.generation)

  function save() {
    if (!next || !gn || sim == null) return
    const auto = gn.survival ? Object.fromEntries(Object.entries(gn.survival.fields).map(([k, f]) => [k, f.alive])) : null
    setLabels((l) => [...l, { key: next.key, generation: next.generation, similarity: sim, fields: { ...Object.fromEntries(FIELDS.map((f) => [f, false])), ...fields }, ts: new Date().toISOString(), clip: gn.metrics.clip_dist_to_g0, hist: gn.metrics.hist_dist_to_g0, ssim: gn.metrics.ssim_to_g0, auto }])
  }
  function download() {
    const head = ['key', 'generation', 'similarity', 'clip_dist_to_g0', 'hist_dist_to_g0', 'ssim_to_g0', ...FIELDS.map((f) => `hand_${f}`), ...FIELDS.map((f) => `auto_${f}`), 'ts']
    const rows = labels.map((l) => [l.key, l.generation, l.similarity, l.clip ?? '', l.hist ?? '', l.ssim ?? '', ...FIELDS.map((f) => (l.fields[f] ? 1 : 0)), ...FIELDS.map((f) => (l.auto ? (l.auto[f] ? 1 : 0) : '')), l.ts])
    const csv = [head, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    a.download = 'labels.csv'
    a.click()
  }

  return (
    <>
      <h1>Hand labelling</h1>
      <p className="muted">
        The automated measures (CLIP distance, extracted attributes) are proxies. This page collects my own judgement on a fixed
        sample of 60 pairs so <code>telephone validate</code> can report how well the proxies agree with a person. Labels are kept in
        this browser only; download the CSV and save it as <code>analysis/validation/labels.csv</code>.
      </p>
      <div className="badges" style={{ marginBottom: 12 }}>
        <span className="badge">{labels.length} / {pairs.length} labelled</span>
        <button onClick={download} disabled={!labels.length}>Download CSV</button>
        <button onClick={() => { if (confirm('Delete all labels in this browser?')) setLabels([]) }} disabled={!labels.length}>Reset</button>
      </div>
      {!next ? <p>All pairs labelled. Download the CSV.</p> : !chain || !g0 || !gn ? <p className="faint">Loading pair…</p> : (
        <>
          <div className="labelgrid">
            <div><div className="faint small">generation 0</div><img src={assetUrl(g0.full ?? g0.thumb)} alt="generation 0" /></div>
            <div><div className="faint small">generation {gn.generation} · {chain.variant} · {chain.station_sequence}</div><img src={assetUrl(gn.full ?? gn.thumb)} alt={`generation ${gn.generation}`} /></div>
          </div>
          <h3 style={{ marginTop: 16 }}>1. Is this still the same picture?</h3>
          <div className="scale">
            {[1, 2, 3, 4, 5].map((v) => <button key={v} className={sim === v ? 'on' : ''} onClick={() => setSim(v)}>{v}</button>)}
            <span className="faint small" style={{ alignSelf: 'center' }}>1 = nothing in common, 3 = same scene, different picture, 5 = indistinguishable</span>
          </div>
          <h3 style={{ marginTop: 16 }}>2. Which of these are still true of the right-hand image?</h3>
          <div className="checks">
            {FIELDS.map((f) => (
              <label key={f}><input type="checkbox" checked={!!fields[f]} onChange={(e) => setFields({ ...fields, [f]: e.target.checked })} /> {FIELD_LABELS[f]}{g0.attributes ? <span className="faint"> ({String(Array.isArray((g0.attributes as never)[f]) ? ((g0.attributes as never)[f] as string[]).join(', ') : (g0.attributes as never)[f])})</span> : null}</label>
            ))}
          </div>
          <div className="controls" style={{ marginTop: 14 }}>
            <button className="primary" onClick={save} disabled={sim == null}>Save and next</button>
            <button onClick={() => setLabels((l) => [...l, { key: next.key, generation: next.generation, similarity: 0, fields: {}, ts: new Date().toISOString(), clip: null, hist: null, ssim: null, auto: null }])}>Skip</button>
          </div>
        </>
      )}
    </>
  )
}

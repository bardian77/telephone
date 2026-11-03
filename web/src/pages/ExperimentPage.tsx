import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import DriftChart, { SERIES_COLORS, type Series } from '../components/DriftChart'
import Stations from '../components/Stations'
import { assetUrl, fmt, FIELD_LABELS, pct, usd, type Index } from '../data'

const METRICS: Array<[string, string, [number, number] | undefined]> = [
  ['clip_dist_to_g0', 'CLIP distance to generation 0', [0, 1]],
  ['hist_dist_to_g0', 'Colour histogram distance to generation 0', [0, 1]],
  ['survival_fraction', 'Fraction of attributes still alive', [0, 1]],
  ['ssim_to_g0', 'SSIM against generation 0', [0, 1]],
]

export default function ExperimentPage({ index }: { index: Index }) {
  const { id = '' } = useParams()
  const exp = index.experiments.find((e) => e.id === id)
  const hasClip = !!exp && Object.values(exp.summary.variants).some((g) => (g.curves.clip_dist_to_g0?.length ?? 0) > 1)
  const [metric, setMetric] = useState(hasClip ? METRICS[0][0] : METRICS[1][0])
  const [groupBy, setGroupBy] = useState<'variants' | 'types'>('variants')
  const [variantFilter, setVariantFilter] = useState<string>('all')
  const series = useMemo<Series[]>(() => {
    if (!exp) return []
    const groups = exp.summary[groupBy]
    return Object.entries(groups).flatMap(([name, g], i) => {
      const pts = (g.curves[metric] ?? []).map((p) => ({ x: p.generation, y: p.mean }))
      return pts.length ? [{ name: `${name} (n=${g.chains})`, color: SERIES_COLORS[i % 8], points: pts }] : []
    })
  }, [exp, metric, groupBy])
  if (!exp) return <p>Unknown experiment {id}.</p>
  const m = METRICS.find((x) => x[0] === metric)!
  const chains = exp.chains.filter((c) => variantFilter === 'all' || c.variant === variantFilter)
  const groups = exp.summary[groupBy]
  const fields = Object.keys(FIELD_LABELS)

  return (
    <>
      <p className="small"><Link to="/">← all experiments</Link></p>
      <h1>{exp.title}</h1>
      {exp.question && <p className="lead muted">{exp.question}</p>}
      {exp.description && <p>{exp.description}</p>}
      <div className="badges">
        <span className="badge">{exp.chains.length} chains</span>
        <span className="badge">{exp.generations ?? '–'} generations each</span>
        {exp.repeats && exp.repeats > 1 ? <span className="badge">{exp.repeats} repeats</span> : null}
        <span className="badge">{usd(exp.cost_usd)} paid</span>
        {exp.extractor && <span className="badge">survival read by {exp.extractor.provider}{exp.extractor.model ? ` / ${exp.extractor.model}` : ''}</span>}
      </div>

      <h2>Variants</h2>
      {exp.variants.map((v) => (
        <div key={v.name} style={{ marginBottom: 6 }}>
          <b>{v.name}</b>{v.notes && <span className="muted small"> — {v.notes}</span>}
          <Stations stations={v.stations} />
        </div>
      ))}

      <h2>Mean drift per {groupBy === 'variants' ? 'variant' : 'photo type'}</h2>
      <div className="controls">
        <select value={metric} onChange={(e) => setMetric(e.target.value)}>{METRICS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <select value={groupBy} onChange={(e) => setGroupBy(e.target.value as 'variants' | 'types')}><option value="variants">by variant</option><option value="types">by photo type</option></select>
      </div>
      <DriftChart series={series} yLabel={m[1]} yDomain={m[2]} height={260} />

      <h2>When does each attribute first fail? (median generation)</h2>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead><tr><th>{groupBy === 'variants' ? 'variant' : 'type'}</th>{fields.map((f) => <th key={f} className="num">{FIELD_LABELS[f]}</th>)}</tr></thead>
          <tbody>
            {Object.entries(groups).map(([name, g]) => (
              <tr key={name}><td>{name}</td>{fields.map((f) => <td key={f} className="num">{g.first_failure_median[f] == null ? <span className="faint">never</span> : `g${g.first_failure_median[f]}`}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="faint small">"never" means the attribute was still alive at the last generation in at least half the chains.</p>

      {Object.values(groups).some((g) => g.errors.length) && (
        <>
          <h2>Failed runs (kept)</h2>
          <ul className="ref small">
            {Object.entries(groups).flatMap(([name, g]) => g.errors.map((e, i) => <li key={name + i}><span className="mono">{e.chain_id}</span> stopped at generation {e.generation}: {e.error}</li>))}
          </ul>
        </>
      )}

      <h2>Chains</h2>
      <div className="controls">
        <select value={variantFilter} onChange={(e) => setVariantFilter(e.target.value)}>
          <option value="all">all variants</option>
          {exp.variants.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
        </select>
        <span className="faint small">{chains.length} shown</span>
      </div>
      <div className="grid">
        {chains.map((c) => (
          <Link key={c.key} to={`/chain/${c.key}`} className="card">
            <div className="pair"><img src={assetUrl(c.thumb0)} alt="generation 0" loading="lazy" /><img src={assetUrl(c.thumb_last)} alt={`generation ${c.last_generation}`} loading="lazy" /></div>
            <div className="title">{c.variant}{c.repeat ? ` · r${c.repeat}` : ''} <span className="muted mono small">{c.image}</span></div>
            <div className="badges">
              <span className="badge">g0 → g{c.last_generation}</span>
              <span className="badge">drift {fmt(c.final_clip ?? c.final_hist)}</span>
              {c.final_survival != null && <span className={`badge ${c.final_survival > 0.5 ? 'alive' : 'dead'}`}>{pct(c.final_survival)} alive</span>}
              {c.errors > 0 && <span className="badge dead">stopped</span>}
            </div>
          </Link>
        ))}
      </div>
      {exp.references?.length ? (<><h2>Context</h2><ul className="ref">{exp.references.map((r) => <li key={r}>{r}</li>)}</ul></>) : null}
    </>
  )
}

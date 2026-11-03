import { useEffect, useMemo, useState } from 'react'
import { assetUrl, fmt, pct, usd, type Chain } from '../data'
import DriftChart, { SERIES_COLORS, type Series } from './DriftChart'
import SurvivalTable from './SurvivalTable'
import Stations from './Stations'

type Props = { chain: Chain; gen?: number; onGen?: (g: number) => void; compact?: boolean }

export default function ChainPlayer({ chain, gen, onGen, compact = false }: Props) {
  const gens = chain.generations.filter((g) => !g.error)
  const [local, setLocal] = useState(0)
  const [playing, setPlaying] = useState(false)
  const current = gen ?? local
  const setGen = (g: number) => { setLocal(g); onGen?.(g) }
  const g = gens[Math.min(current, gens.length - 1)]

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setGen((current + 1) % gens.length), 900)
    return () => clearInterval(id)
  })

  const series = useMemo<Series[]>(() => {
    const pts = (f: (x: Chain['generations'][number]) => number | null | undefined) =>
      gens.map((x) => ({ x: x.generation, y: f(x) })).filter((p): p is { x: number; y: number } => p.y != null)
    const s: Series[] = []
    const clip = pts((x) => x.metrics.clip_dist_to_g0)
    if (clip.length) s.push({ name: 'CLIP distance to g0', color: SERIES_COLORS[0], points: clip })
    s.push({ name: 'histogram distance to g0', color: SERIES_COLORS[1], points: pts((x) => x.metrics.hist_dist_to_g0) })
    const surv = pts((x) => (x.survival ? x.survival.alive_count / x.survival.total : null))
    if (surv.length) s.push({ name: 'attributes alive', color: SERIES_COLORS[2], points: surv })
    s.push({ name: 'SSIM to g0', color: SERIES_COLORS[3], points: pts((x) => x.metrics.ssim_to_g0) })
    return s
  }, [chain])

  if (!g) return <p className="faint">This chain has no successful generations.</p>

  return (
    <div className={compact ? '' : 'player'}>
      <div>
        <div className="stage">
          <img src={assetUrl(g.full ?? g.thumb)} alt={`generation ${g.generation}`} />
          <span className="tag">generation {g.generation} of {chain.last_generation}</span>
        </div>
        <div className="controls">
          <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'pause' : 'play'}>{playing ? '❚❚' : '▶'}</button>
          <button onClick={() => setGen(Math.max(0, current - 1))} disabled={current === 0}>‹</button>
          <input type="range" min={0} max={gens.length - 1} value={Math.min(current, gens.length - 1)} onChange={(e) => { setPlaying(false); setGen(Number(e.target.value)) }} />
          <button onClick={() => setGen(Math.min(gens.length - 1, current + 1))} disabled={current >= gens.length - 1}>›</button>
          <span className="mono small">g{g.generation}</span>
        </div>
        <div className="strip">
          {gens.map((x, i) => (
            <button key={x.generation} className={i === current ? 'current' : ''} onClick={() => { setPlaying(false); setGen(i) }} title={`generation ${x.generation}`}>
              <img src={assetUrl(x.thumb)} alt="" loading="lazy" />
              <div className="g">{x.generation}</div>
            </button>
          ))}
        </div>
        {!compact && (
          <>
            <h3 style={{ marginTop: 12 }}>Drift</h3>
            <DriftChart series={series} yLabel="distance" yDomain={[0, 1]} cursor={g.generation} onCursor={(x) => { if (x != null) { const i = gens.findIndex((q) => q.generation === x); if (i >= 0) setGen(i) } }} />
          </>
        )}
      </div>
      <div>
        {g.caption != null && (
          <div className="caption">
            <div className="label">{g.generation === 0 ? 'original photograph' : `caption that produced generation ${g.generation}`}</div>
            {g.caption}
          </div>
        )}
        {g.generation === 0 && <div className="caption"><div className="label">generation 0</div>The photograph as it entered the chain.</div>}
        <div className="badges" style={{ margin: '10px 0' }}>
          <span className="badge">clip {fmt(g.metrics.clip_dist_to_g0)}</span>
          <span className="badge">hist {fmt(g.metrics.hist_dist_to_g0)}</span>
          <span className="badge">ssim {fmt(g.metrics.ssim_to_g0)}</span>
          {g.survival && <span className={`badge ${g.survival.alive_count / g.survival.total > 0.5 ? 'alive' : 'dead'}`}>{g.survival.alive_count}/{g.survival.total} attributes alive</span>}
          {g.metrics.face_count != null && <span className="badge">{g.metrics.face_count} face{g.metrics.face_count === 1 ? '' : 's'}</span>}
          {g.metrics.ocr_words != null && <span className="badge">OCR {g.metrics.ocr_words} words</span>}
          <span className="badge">{g.metrics.width}×{g.metrics.height} · {g.metrics.file_bytes ? `${Math.round(g.metrics.file_bytes / 1024)} KB` : ''}</span>
          <span className="badge">{usd(g.cost_usd)}{g.list_price_usd > g.cost_usd ? ` (list ${usd(g.list_price_usd)})` : ''}</span>
        </div>
        {!compact && (
          <>
            <h3>What survived</h3>
            <SurvivalTable survival={g.survival} firstFailure={chain.first_failure} />
            <h3 style={{ marginTop: 16 }}>Stations this generation</h3>
            {g.stations.length ? (
              <table>
                <thead><tr><th>station</th><th>system</th><th className="num">ms</th><th className="num">cost</th></tr></thead>
                <tbody>
                  {g.stations.map((s, i) => (
                    <tr key={i}>
                      <td>{s.kind}{s.cached ? <span className="faint small"> cached</span> : ''}{s.error ? <div className="small" style={{ color: 'var(--dead)' }}>{s.error}</div> : null}</td>
                      <td className="small">{s.provider}{s.model ? ` / ${s.model}` : ''}{s.seed != null ? <span className="faint"> seed {s.seed}</span> : ''}</td>
                      <td className="num">{s.latency_ms}</td>
                      <td className="num">{usd(s.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="faint small">Generation 0 has no stations.</p>}
            <details style={{ marginTop: 12 }}>
              <summary>Chain configuration</summary>
              <Stations stations={chain.stations ?? undefined} />
              <dl className="kv">
                <dt>chain</dt><dd className="mono small">{chain.chain_id}</dd>
                <dt>seed</dt><dd>{chain.seed}</dd>
                <dt>repeat</dt><dd>{chain.repeat}</dd>
                <dt>total cost</dt><dd>{usd(chain.cost_usd)} paid{chain.list_price_usd > chain.cost_usd ? `, ${usd(chain.list_price_usd)} at list price` : ''}</dd>
                <dt>final survival</dt><dd>{pct(gens[gens.length - 1].survival ? gens[gens.length - 1].survival!.alive_count / gens[gens.length - 1].survival!.total : null)}</dd>
              </dl>
              {chain.errors.length > 0 && <p className="small" style={{ color: 'var(--dead)' }}>Stopped at generation {chain.errors[0].generation}: {chain.errors[0].error}</p>}
            </details>
          </>
        )}
      </div>
    </div>
  )
}

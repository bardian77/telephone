import { Link, useParams } from 'react-router-dom'
import { assetUrl, fmt, pct, type Index } from '../data'

export default function Photo({ index }: { index: Index }) {
  const { image = '' } = useParams()
  const chains = index.experiments.flatMap((e) => e.chains.map((c) => ({ ...c, experiment: e }))).filter((c) => c.image === image)
  if (!chains.length) return <p>No chains for {image}.</p>
  return (
    <>
      <h1 className="mono">{image}</h1>
      <div className="two" style={{ alignItems: 'start' }}>
        <img src={assetUrl(chains[0].thumb0)} alt={image} style={{ width: '100%', borderRadius: 10 }} />
        <div>
          <p className="muted">{chains.length} chains start from this photograph. Each card shows the first and the last generation.</p>
          <p className="small"><Link to={`/compare?a=${chains[0].key}${chains[1] ? `&b=${chains[1].key}` : ''}`}>Compare two chains side by side →</Link></p>
        </div>
      </div>
      <div className="grid" style={{ marginTop: 18 }}>
        {chains.map((c) => (
          <Link key={c.key} to={`/chain/${c.key}`} className="card">
            <div className="pair"><img src={assetUrl(c.thumb0)} alt="generation 0" /><img src={assetUrl(c.thumb_last)} alt={`generation ${c.last_generation}`} /></div>
            <div className="title">{c.experiment.title.replace(/^Experiment \d+: /, '')} · {c.variant}{c.repeat ? ` · repeat ${c.repeat}` : ''}</div>
            <div className="muted small">{c.station_sequence}</div>
            <div className="badges">
              <span className="badge">{c.last_generation} generations</span>
              <span className="badge">drift {fmt(c.final_clip ?? c.final_hist)}</span>
              {c.final_survival != null && <span className={`badge ${c.final_survival > 0.5 ? 'alive' : 'dead'}`}>{pct(c.final_survival)} alive</span>}
              {c.errors > 0 && <span className="badge dead">stopped</span>}
            </div>
          </Link>
        ))}
      </div>
    </>
  )
}

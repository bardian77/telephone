import { Link } from 'react-router-dom'
import { assetUrl, usd, type Index } from '../data'

export default function Home({ index }: { index: Index }) {
  const chains = index.experiments.flatMap((e) => e.chains)
  const byImage = new Map<string, typeof chains>()
  for (const c of chains) byImage.set(c.image, [...(byImage.get(c.image) ?? []), c])
  const real = index.experiments.filter((e) => !e.id.startsWith('exp00') && e.id !== 'adhoc')
  return (
    <>
      <section className="hero">
        <h1>What does a photograph keep and lose as it passes repeatedly through the systems that circulate and interpret it?</h1>
        <p className="lead muted">
          Telephone takes one of my photographs and sends it round a loop: a platform recompresses it, a vision model describes it,
          an image model redraws it from the description, and the result goes round again. At every generation the pipeline records
          how far the picture has drifted and which of its readable attributes are still alive.
        </p>
        <div className="stats">
          <div className="stat"><b>{index.totals.chains}</b><span>chains</span></div>
          <div className="stat"><b>{index.totals.generations}</b><span>generations</span></div>
          <div className="stat"><b>{byImage.size}</b><span>starting photographs</span></div>
          <div className="stat"><b>{usd(index.totals.paid_usd)}</b><span>paid for API calls{index.totals.list_price_usd > index.totals.paid_usd ? ` (${usd(index.totals.list_price_usd)} at list price)` : ''}</span></div>
        </div>
      </section>

      <h2>Experiments</h2>
      <div className="grid">
        {(real.length ? real : index.experiments).map((e) => (
          <Link key={e.id} to={`/experiments/${e.id}`} className="card">
            <div className="title">{e.title}</div>
            <div className="muted small">{e.question}</div>
            <div className="badges"><span className="badge">{e.chains.length} chains</span><span className="badge">{e.variants.length} variants</span></div>
          </Link>
        ))}
      </div>

      <h2>Photographs</h2>
      <p className="muted small">Choose a photograph to see every chain it went through.</p>
      <div className="grid">
        {[...byImage.entries()].map(([img, cs]) => (
          <Link key={img} to={`/photo/${encodeURIComponent(img)}`} className="card">
            <img src={assetUrl(cs[0].thumb0)} alt={img} loading="lazy" />
            <div className="title mono small">{img}</div>
            <div className="badges"><span className="badge">{cs[0].type}</span><span className="badge">{cs.length} chains</span></div>
          </Link>
        ))}
      </div>
    </>
  )
}

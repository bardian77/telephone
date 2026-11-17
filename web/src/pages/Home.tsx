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
        <h1>The lab</h1>
        <p className="lead muted">
          Every chain as the pipeline recorded it, with all of its measurements. {index.totals.chains} chains,{' '}
          {index.totals.generations} generations, {usd(index.totals.paid_usd)} paid for API calls.
        </p>
      </section>

      <h2>Experiments</h2>
      <div className="grid">
        {(real.length ? real : index.experiments).map((e) => (
          <Link key={e.id} to={`/lab/experiments/${e.id}`} className="card">
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
          <Link key={img} to={`/lab/photo/${encodeURIComponent(img)}`} className="card">
            <img src={assetUrl(cs[0].thumb0)} alt={img} loading="lazy" />
            <div className="title mono small">{img}</div>
            <div className="badges"><span className="badge">{cs[0].type}</span><span className="badge">{cs.length} chains</span></div>
          </Link>
        ))}
      </div>
    </>
  )
}

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ChainPlayer from '../components/ChainPlayer'
import { loadChain, type Chain, type Index } from '../data'

export default function ChainPage({ index }: { index: Index }) {
  const { key = '' } = useParams()
  const [chain, setChain] = useState<Chain | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setChain(null); loadChain(key).then(setChain).catch((e) => setErr(String(e))) }, [key])
  if (err) return <p>{err}</p>
  if (!chain) return <p className="faint">Loading…</p>
  const exp = index.experiments.find((e) => e.id === chain.experiment_id)
  const siblings = exp?.chains.filter((c) => c.image === chain.image && c.key !== chain.key) ?? []
  return (
    <>
      <p className="small"><Link to={`/experiments/${chain.experiment_id}`}>← {exp?.title ?? chain.experiment_id}</Link> · <Link to={`/photo/${encodeURIComponent(chain.image)}`}>{chain.image}</Link></p>
      <h1>{chain.variant}{chain.repeat ? ` · repeat ${chain.repeat}` : ''} <span className="muted" style={{ fontWeight: 400 }}>on {chain.image}</span></h1>
      <p className="muted">{chain.station_sequence}, repeated {chain.last_generation} times.</p>
      <ChainPlayer chain={chain} />
      {siblings.length > 0 && (
        <p className="small" style={{ marginTop: 18 }}>
          Compare with: {siblings.map((s) => <Link key={s.key} to={`/compare?a=${chain.key}&b=${s.key}`} style={{ marginRight: 10 }}>{s.variant}{s.repeat ? ` r${s.repeat}` : ''}</Link>)}
        </p>
      )}
    </>
  )
}

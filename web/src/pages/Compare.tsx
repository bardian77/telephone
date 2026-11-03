import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ChainPlayer from '../components/ChainPlayer'
import { loadChain, type Chain, type Index } from '../data'

export default function Compare({ index }: { index: Index }) {
  const [params, setParams] = useSearchParams()
  const all = index.experiments.flatMap((e) => e.chains)
  const a = params.get('a') ?? all[0]?.key ?? ''
  const b = params.get('b') ?? all[1]?.key ?? ''
  const [ca, setCa] = useState<Chain | null>(null)
  const [cb, setCb] = useState<Chain | null>(null)
  const [gen, setGen] = useState(0)
  useEffect(() => { if (a) loadChain(a).then(setCa) }, [a])
  useEffect(() => { if (b) loadChain(b).then(setCb) }, [b])
  const pick = (which: 'a' | 'b') => (e: React.ChangeEvent<HTMLSelectElement>) => { params.set(which, e.target.value); setParams(params) }
  const label = (c: typeof all[number]) => `${c.experiment_id.replace(/^exp\d+_/, '')} · ${c.variant}${c.repeat ? ` r${c.repeat}` : ''} · ${c.image}`
  return (
    <>
      <h1>Compare two chains</h1>
      <p className="muted">The scrubber moves both chains together. Pick any two chains, ideally the same photograph through different stations.</p>
      <div className="controls">
        <input type="range" min={0} max={Math.max(ca?.last_generation ?? 0, cb?.last_generation ?? 0)} value={gen} onChange={(e) => setGen(Number(e.target.value))} />
        <span className="mono small">g{gen}</span>
      </div>
      <div className="two">
        {[['a', a, ca, setCa] as const, ['b', b, cb, setCb] as const].map(([which, key, chain]) => (
          <div key={which}>
            <select value={key} onChange={pick(which)} style={{ maxWidth: '100%', marginBottom: 8 }}>
              {all.map((c) => <option key={c.key} value={c.key}>{label(c)}</option>)}
            </select>
            {chain ? <ChainPlayer chain={chain} gen={Math.min(gen, chain.last_generation)} onGen={setGen} compact /> : <p className="faint">Loading…</p>}
          </div>
        ))}
      </div>
    </>
  )
}

import { useEffect, useRef, useState } from 'react'
import ChainPlayer from '../components/ChainPlayer'
import { assetUrl, type Chain, type Index } from '../data'

const API = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'

type Status = { enabled: boolean; remaining_usd?: number; daily_cap_usd?: number; presets?: Record<string, string>; max_generations?: number }
type Job = { id: string; status: 'queued' | 'running' | 'done' | 'error'; chain: Chain | null; error?: string; position?: number }

export default function Live({ index }: { index: Index }) {
  const [status, setStatus] = useState<Status | null>(null)
  const images = index.experiments.flatMap((e) => e.chains).reduce((m, c) => (m.has(c.image) ? m : m.set(c.image, c.thumb0)), new Map<string, string | null>())
  const [image, setImage] = useState<string>('')
  const [preset, setPreset] = useState('telephone')
  const [gens, setGens] = useState(4)
  const [job, setJob] = useState<Job | null>(null)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    fetch(`${API}/live/status`).then((r) => (r.ok ? r.json() : { enabled: false })).then(setStatus).catch(() => setStatus({ enabled: false }))
  }, [])
  useEffect(() => { if (!image && images.size) setImage([...images.keys()][0]) }, [images.size])
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current) }, [])

  async function start() {
    const r = await fetch(`${API}/live`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ image, preset, generations: gens }) })
    if (!r.ok) { setJob({ id: '', status: 'error', chain: null, error: (await r.json().catch(() => ({})))?.detail ?? r.statusText }); return }
    const j = (await r.json()) as Job
    setJob(j)
    const poll = async () => {
      const p = await fetch(`${API}/live/${j.id}`)
      if (!p.ok) return
      const pj = (await p.json()) as Job
      setJob(pj)
      if (pj.status === 'queued' || pj.status === 'running') timer.current = window.setTimeout(poll, 2500)
    }
    timer.current = window.setTimeout(poll, 1500)
  }

  if (status == null) return <p className="faint">Checking whether live runs are enabled…</p>
  return (
    <>
      <h1>Run a chain live</h1>
      {!status.enabled ? (
        <div className="banner">
          Live runs are switched off on this deployment, so the site never spends money on its own. Everything else on the site is a
          recording of chains that already ran. To run live, start the API with <code>TELEPHONE_LIVE=1</code> and provider keys.
        </div>
      ) : (
        <>
          <p className="muted">Pick one of my photographs and a chain. Live runs are rate limited per visitor and capped per day (remaining today: ${status.remaining_usd?.toFixed(2)} of ${status.daily_cap_usd?.toFixed(2)}). Results are cached, so repeating a run is free.</p>
          <div className="grid" style={{ marginBottom: 12 }}>
            {[...images.entries()].map(([img, thumb]) => (
              <button key={img} className="card" style={{ borderColor: img === image ? 'var(--accent)' : undefined }} onClick={() => setImage(img)}>
                <img src={assetUrl(thumb)} alt={img} /><div className="mono small">{img}</div>
              </button>
            ))}
          </div>
          <div className="controls">
            <select value={preset} onChange={(e) => setPreset(e.target.value)}>
              {Object.entries(status.presets ?? { telephone: 'platform → caption → regenerate' }).map(([k, v]) => <option key={k} value={k}>{k}: {v}</option>)}
            </select>
            <label>generations <input type="number" min={1} max={status.max_generations ?? 6} value={gens} onChange={(e) => setGens(Number(e.target.value))} style={{ width: 64 }} /></label>
            <button className="primary" onClick={start} disabled={!image || job?.status === 'running' || job?.status === 'queued'}>Run</button>
          </div>
        </>
      )}
      {job && (
        <div style={{ marginTop: 16 }}>
          {job.status === 'error' && <p style={{ color: 'var(--dead)' }}>{job.error}</p>}
          {(job.status === 'queued' || job.status === 'running') && <p className="faint">{job.status}{job.position ? ` (position ${job.position})` : ''}… generations appear as they finish.</p>}
          {job.chain && <ChainPlayer chain={job.chain} />}
        </div>
      )}
    </>
  )
}

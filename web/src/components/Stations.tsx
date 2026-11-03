type S = { kind: string; provider?: string | null; model?: string | null; params?: Record<string, unknown> }

const DESC: Record<string, string> = {
  platform: 'recompress, resize, strip metadata',
  caption: 'a vision model describes it',
  regenerate: 'a text-to-image model redraws it',
  extract: 'structured reading for survival',
  physical: 'photograph of a screen',
}

export default function Stations({ stations, compact = false }: { stations: S[] | null | undefined; compact?: boolean }) {
  if (!stations?.length) return null
  return (
    <div className="stations">
      {stations.map((s, i) => (
        <span key={i} style={{ display: 'contents' }}>
          <span className="station">
            <b>{s.kind}</b>
            {!compact && (
              <span className="muted small">
                {s.provider ? `${s.provider}${s.model ? ` / ${s.model}` : ''}` : DESC[s.kind]}
                {s.params && Object.keys(s.params).length ? ` · ${Object.entries(s.params).map(([k, v]) => `${k}=${String(v)}`).join(' ')}` : ''}
              </span>
            )}
          </span>
          {i < stations.length - 1 && <span className="arrow">→</span>}
        </span>
      ))}
      <span className="arrow">↻ repeat</span>
    </div>
  )
}

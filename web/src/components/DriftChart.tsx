import { useMemo, useRef, useState } from 'react'

export type Series = { name: string; color: string; points: Array<{ x: number; y: number }>; faint?: boolean }

type Props = {
  series: Series[]
  yLabel: string
  yDomain?: [number, number]
  cursor?: number | null
  onCursor?: (x: number | null) => void
  height?: number
  format?: (v: number) => string
}

/** Small SVG line chart: 2px lines, hairline grid, hover crosshair + tooltip, legend for 2+ series. */
export default function DriftChart({ series, yLabel, yDomain, cursor, onCursor, height = 220, format = (v) => v.toFixed(2) }: Props) {
  const ref = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const W = 640, H = height, m = { l: 44, r: 14, t: 12, b: 28 }
  const visible = series.filter((s) => s.points.length)
  const xs = visible.flatMap((s) => s.points.map((p) => p.x))
  const ys = visible.flatMap((s) => s.points.map((p) => p.y))
  const xMax = Math.max(1, ...xs)
  const [y0, y1] = yDomain ?? [Math.min(0, ...ys), Math.max(0.0001, ...ys) * 1.05]
  const sx = (x: number) => m.l + (x / xMax) * (W - m.l - m.r)
  const sy = (y: number) => m.t + (1 - (y - y0) / (y1 - y0 || 1)) * (H - m.t - m.b)
  const ticks = useMemo(() => {
    const n = 4
    return Array.from({ length: n + 1 }, (_, i) => y0 + ((y1 - y0) * i) / n)
  }, [y0, y1])
  const active = cursor ?? hover
  const named = visible.filter((s) => !s.faint)

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    const px = ((e.clientX - r.left) / r.width) * W
    const x = Math.round(((px - m.l) / (W - m.l - m.r)) * xMax)
    const cx = Math.max(0, Math.min(xMax, x))
    setHover(cx)
    onCursor?.(cx)
  }
  function onLeave() {
    setHover(null)
    onCursor?.(null)
  }

  if (!visible.length) return <p className="faint small">No data for {yLabel}.</p>

  return (
    <div style={{ position: 'relative' }}>
      {named.length >= 2 && (
        <div className="legend">
          {named.map((s) => (
            <span key={s.name}><i className="key" style={{ background: s.color }} />{s.name}</span>
          ))}
        </div>
      )}
      <svg ref={ref} className="chart" viewBox={`0 0 ${W} ${H}`} onMouseMove={onMove} onMouseLeave={onLeave} role="img" aria-label={yLabel}>
        <g className="grid">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={m.l} x2={W - m.r} y1={sy(t)} y2={sy(t)} />
              <text x={m.l - 6} y={sy(t) + 4} textAnchor="end">{format(t)}</text>
            </g>
          ))}
        </g>
        <line className="axis" x1={m.l} x2={W - m.r} y1={H - m.b} y2={H - m.b} />
        {Array.from({ length: xMax + 1 }, (_, i) => i).filter((i) => xMax <= 14 || i % Math.ceil(xMax / 10) === 0).map((i) => (
          <text key={i} x={sx(i)} y={H - m.b + 16} textAnchor="middle">{i}</text>
        ))}
        <text x={W / 2} y={H - 2} textAnchor="middle">generation</text>
        {visible.map((s, i) => (
          <polyline key={s.name + i} className="series" points={s.points.map((p) => `${sx(p.x)},${sy(p.y)}`).join(' ')} stroke={s.color} opacity={s.faint ? 0.25 : 1} strokeWidth={s.faint ? 1 : 2} />
        ))}
        {named.map((s) => s.points.map((p) => <circle key={`${s.name}-${p.x}`} cx={sx(p.x)} cy={sy(p.y)} r={3.5} fill={s.color} />))}
        {active != null && <line className="cursor" x1={sx(active)} x2={sx(active)} y1={m.t} y2={H - m.b} />}
      </svg>
      {active != null && (
        <div className="tooltip" style={{ left: `${(sx(active) / W) * 100}%`, top: 0, transform: sx(active) > W * 0.6 ? 'translateX(-105%)' : 'translateX(8px)' }}>
          <div><b>generation {active}</b></div>
          {named.map((s) => {
            const p = s.points.find((q) => q.x === active)
            return p ? <div key={s.name}><i className="key" style={{ background: s.color, display: 'inline-block', width: 10, height: 2, marginRight: 6, verticalAlign: 'middle' }} />{s.name}: {format(p.y)}</div> : null
          })}
        </div>
      )}
    </div>
  )
}

export const SERIES_COLORS = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)', 'var(--s7)', 'var(--s8)']

import { JOURNEYS, percent } from '../site'

type Line = { id: string; values: Array<number | null> }

type Props = {
  lines: Line[]
  selected: string
  current: number
  /** What the line measures, for the screen-reader summary. */
  label: string
}

/** One hand-written SVG line chart: share of fine detail left (0 to 100%) against the pass
 * number. The chosen journey is drawn strong, the others faint, each named at its end. */
export default function DetailLine({ lines, selected, current, label }: Props) {
  const W = 640, H = 240, m = { l: 44, r: 150, t: 14, b: 34 }
  const last = Math.max(1, ...lines.map((l) => l.values.length - 1))
  const sx = (x: number) => m.l + (x / last) * (W - m.l - m.r)
  const sy = (y: number) => m.t + (1 - Math.min(1, Math.max(0, y))) * (H - m.t - m.b)
  const name = (id: string) => JOURNEYS.find((j) => j.id === id)?.label ?? id
  const path = (values: Array<number | null>) =>
    values
      .map((v, i) => (v == null ? null : `${sx(i)},${sy(v)}`))
      .filter(Boolean)
      .join(' ')
  const end = (values: Array<number | null>) => {
    for (let i = values.length - 1; i >= 0; i--) if (values[i] != null) return { x: i, y: values[i] as number }
    return null
  }
  // keep the names at the ends of the lines from sitting on top of each other
  const ends = lines
    .map((l) => ({ id: l.id, at: end(l.values) }))
    .filter((e): e is { id: string; at: { x: number; y: number } } => e.at != null)
    .sort((a, b) => sy(a.at.y) - sy(b.at.y))
  let floor = -Infinity
  const labelY = new Map<string, number>()
  for (const e of ends) {
    const y = Math.max(sy(e.at.y), floor + 14)
    labelY.set(e.id, y)
    floor = y
  }
  const summary = ends
    .map((e) => `${name(e.id)}: ${percent(e.at.y)} after ${e.at.x} passes`)
    .join('; ')

  return (
    <figure className="line">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}. ${summary}.`}>
        <g className="grid">
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={m.l} x2={W - m.r} y1={sy(t)} y2={sy(t)} />
              <text x={m.l - 8} y={sy(t) + 4} textAnchor="end">{percent(t)}</text>
            </g>
          ))}
        </g>
        {[0, 10, 20, 30, 40].filter((t) => t <= last).map((t) => (
          <text key={t} x={sx(t)} y={H - m.b + 16} textAnchor="middle">{t}</text>
        ))}
        <text x={(m.l + W - m.r) / 2} y={H - 4} textAnchor="middle">pass</text>
        {current <= last && <line className="cursor" x1={sx(current)} x2={sx(current)} y1={m.t} y2={H - m.b} />}
        {lines.map((l) => (
          <polyline
            key={l.id}
            className={l.id === selected ? 'series on' : 'series off'}
            points={path(l.values)}
          />
        ))}
        {ends.map((e) => (
          <text
            key={e.id}
            className={e.id === selected ? 'end on' : 'end'}
            x={sx(e.at.x) + 8}
            y={(labelY.get(e.id) ?? sy(e.at.y)) + 4}
          >
            {name(e.id)}
          </text>
        ))}
      </svg>
    </figure>
  )
}

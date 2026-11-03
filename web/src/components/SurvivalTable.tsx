import { FIELD_LABELS, showValue, type Survival } from '../data'

export default function SurvivalTable({ survival, firstFailure }: { survival: Survival | null; firstFailure?: Record<string, number | null> }) {
  if (!survival) return <p className="faint small">No attribute extraction for this generation.</p>
  return (
    <table>
      <thead>
        <tr><th>attribute</th><th>generation 0</th><th>now</th><th className="num">score</th>{firstFailure && <th className="num">first lost</th>}</tr>
      </thead>
      <tbody>
        {Object.entries(survival.fields).map(([k, f]) => (
          <tr key={k}>
            <td><span className={`dot ${f.alive ? 'alive' : 'dead'}`} />{FIELD_LABELS[k] ?? k}</td>
            <td className="muted">{showValue(f.g0)}</td>
            <td>{showValue(f.now)}</td>
            <td className="num">{f.score.toFixed(2)}</td>
            {firstFailure && <td className="num">{firstFailure[k] == null ? 'never' : `g${firstFailure[k]}`}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

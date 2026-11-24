import type { AuditEvent } from '../shared/types'
import { Empty } from '../shared/ui'

export interface RankedHit {
  path: string
  kind: string
  start_line: number
  end_line: number
  score: number
  reasons: string[]
}

/** Ranked hits recorded by the CONTEXT_RETRIEVED audit event (payload.ranked), or [] when absent. */
export function rankedHits(events: AuditEvent[] | null): RankedHit[] {
  const ev = events?.find((e) => e.to_state === 'CONTEXT_RETRIEVED')
  const r = ev?.payload?.ranked
  return Array.isArray(r) ? (r as RankedHit[]) : []
}

/** Why each hit was retrieved: its reasons rendered as a path of steps (anchor, graph hops, hit). */
export function HitPath({ hits }: { hits: RankedHit[] }) {
  if (hits.length === 0) {
    return (
      <Empty title="No ranked hits recorded" compact>
        Retrieval has not run for this incident, or it ran before hits were recorded.
      </Empty>
    )
  }
  return (
    <ol className="hitpath" aria-label="Retrieved hits" style={{ listStyle: 'none', margin: 0, padding: 16 }}>
      {hits.map((h, i) => (
        <li key={`${h.path}:${h.start_line}`} style={{ marginBottom: 12 }}>
          <div>
            <span className="muted">#{i + 1}</span>{' '}
            <span className="mono">
              {h.path}:{h.start_line}-{h.end_line}
            </span>{' '}
            <span className="tag">{h.kind}</span> <span className="muted">score {h.score.toFixed(2)}</span>
          </div>
          <div className="muted" aria-label={`Why hit ${i + 1} was retrieved`}>
            {h.reasons.map((r, j) => (
              <span key={j}>
                {j > 0 && ' → '}
                {r}
              </span>
            ))}
          </div>
        </li>
      ))}
    </ol>
  )
}

import type { AuditEvent } from '../shared/types'
import { Empty, Time } from '../shared/ui'

/** Every recorded action of an incident, oldest first, so a reviewer can see nothing happened off the record. */
export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return <Empty title="No audit events" compact />
  const ordered = [...events].sort((a, b) => a.id - b.id)
  return (
    <ol className="audit" aria-label="Audit timeline" style={{ listStyle: 'none', margin: 0, padding: 16 }}>
      {ordered.map((e) => (
        <li key={e.id} style={{ marginBottom: 12 }}>
          <div>
            <strong>{e.event_type}</strong> <span className="muted">by {e.actor}</span>{' '}
            {e.to_state && (
              <span className="mono">
                {e.from_state ? `${e.from_state} → ` : ''}
                {e.to_state}
              </span>
            )}{' '}
            <Time iso={e.created_at} />
          </div>
          <details>
            <summary className="muted">
              payload <span className="mono">{e.payload_sha256.slice(0, 12)}</span>
            </summary>
            <pre className="mono">{JSON.stringify(e.payload, null, 2)}</pre>
          </details>
        </li>
      ))}
    </ol>
  )
}

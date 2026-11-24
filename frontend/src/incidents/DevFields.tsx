import type { ReactNode } from 'react'

const REASONS: Record<string, string> = {
  insufficient_evidence: 'The model abstained: the collected evidence does not support a diagnosis.',
  invalid_output: 'The model kept submitting invalid output; no diagnosis was accepted.',
  budget_exhausted: 'The tool-call budget ran out before a valid diagnosis was submitted.',
  unsupported_target: 'The diagnosed target cannot be patched (path, symbol or config key not permitted/found).',
  edit_outside_diagnosed_target: 'The proposed edit touched code outside the diagnosed target and was rejected.',
}

const text = (v: unknown): string | null => (typeof v === 'string' && v ? v : typeof v === 'number' ? String(v) : null)

/** First non-empty value for any of the keys across the given audit payloads (absent fields render nothing). */
function pick(payloads: (Record<string, unknown> | undefined)[], keys: string[]): unknown {
  for (const p of payloads) for (const k of keys) if (p && p[k] != null && p[k] !== '') return p[k]
  return null
}

const show = (v: unknown): ReactNode =>
  typeof v === 'string' ? <span className="prewrap">{v}</span> : typeof v === 'number' ? String(v) : <code>{JSON.stringify(v)}</code>

/** Optional dev-pipeline fields from audit payloads: confidence, observed symptom, reconciliation, failure reason. */
export function DevFields({ payloads }: { payloads: (Record<string, unknown> | undefined)[] }) {
  const confidence = pick(payloads, ['confidence'])
  const symptom = text(pick(payloads, ['observed_symptom']))
  const recon = pick(payloads, ['reconciliation'])
  const reason = text(pick(payloads, ['failure_reason', 'reason']))
  const known = reason ? REASONS[reason.split(':')[0]] : undefined
  const rows: [string, ReactNode][] = []
  if (confidence != null) rows.push(['Confidence', show(confidence)])
  if (symptom) rows.push(['Observed symptom', show(symptom)])
  if (recon != null) rows.push(['Reconciliation', show(recon)])
  if (reason)
    rows.push([
      'Reason',
      <>
        <code>{reason}</code>
        {known && <span className="muted"> {known}</span>}
      </>,
    ])
  if (rows.length === 0) return null
  return (
    <dl className="kv" aria-label="Pipeline details">
      {rows.map(([k, v]) => (
        <div key={k} className="kvrow">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

import { useEffect, useState } from 'react'
import { apiGet, errorMessage } from '../shared/api'
import { ErrorBox, Loading, PageHeader } from '../shared/ui'

export interface Paired {
  a: string
  b: string
  metric: string
  n_paired: number
  mean_a: number | null
  mean_b: number | null
  mean_diff: number | null
  b_better: number
  b_worse: number
  tied: number
  ci95: [number, number] | null
  ci_note: string | null
}

const pct = (v: number | null | undefined) => (typeof v !== 'number' || !Number.isFinite(v) ? 'n/a' : `${(v * 100).toFixed(1)}%`)
const cnt = (v: number | null | undefined) => (typeof v === 'number' ? String(v) : 'n/a')

/** Paired differences between conditions; a 95% CI is shown only when the backend computed one. */
export function PairedTable({ rows }: { rows: Paired[] }) {
  if (rows.length === 0) return <p className="muted">No paired comparison is available. Either fewer than two conditions were selected or the report contains no paired results; no numbers are shown.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Comparison</th>
            <th>n</th>
            <th>Mean A</th>
            <th>Mean B</th>
            <th>B − A</th>
            <th>95% CI</th>
            <th>B better / worse / tied</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.metric}-${r.a}-${r.b}`}>
              <td>{r.metric}</td>
              <td>
                {r.a} → {r.b}
              </td>
              <td>{cnt(r.n_paired)}</td>
              <td>{pct(r.mean_a)}</td>
              <td>{pct(r.mean_b)}</td>
              <td>{pct(r.mean_diff)}</td>
              <td>
                {Array.isArray(r.ci95) ? (
                  `[${pct(r.ci95[0])}, ${pct(r.ci95[1])}]`
                ) : (
                  <span className="muted">{r.ci_note ?? 'none'}</span>
                )}
              </td>
              <td>
                {cnt(r.b_better)} / {cnt(r.b_worse)} / {cnt(r.tied)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function FactorialView({ runIds }: { runIds: string[] }) {
  const [rows, setRows] = useState<Paired[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const q = runIds.map((r) => `run_ids=${encodeURIComponent(r)}`).join('&')
    apiGet<{ paired?: Paired[] }>(`/evaluation/report?${q}`)
      .then((r) => setRows(Array.isArray(r?.paired) ? r.paired : []))
      .catch((e) => setError(errorMessage(e)))
  }, [runIds])
  return (
    <>
      <PageHeader title="Condition comparison" />
      {error ? <ErrorBox>{error}</ErrorBox> : rows === null ? <Loading label="Loading comparison" /> : <PairedTable rows={rows} />}
    </>
  )
}

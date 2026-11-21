import { useEffect, useState } from 'react'
import { apiGet, errorMessage } from '../shared/api'
import { runHref } from '../shared/router'
import type { RunSummary } from '../shared/types'
import { Empty, ErrorBox, Loading, PageHeader, Time } from '../shared/ui'
import { completeness } from './format'

export function RunList() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setRuns(null)
    setError(null)
    apiGet<RunSummary[]>('/evaluation/runs')
      .then((r) => !cancelled && setRuns(r))
      .catch((e) => !cancelled && setError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  return (
    <>
      <PageHeader
        title="Evaluation runs"
        sub="Raw counts per run. Computed metrics (Recall@K, MRR, repair rate) are shown on each run when the report endpoint can produce them."
      />
      {error && <ErrorBox onRetry={() => setReloadKey((k) => k + 1)}>Could not load runs: {error}</ErrorBox>}
      <section className="card" aria-label="Runs">
        {!runs && !error && <Loading label="Loading runs…" lines={5} />}
        {runs && runs.length === 0 && (
          <Empty title="No evaluation runs found.">Start one with the experiment runner; it appears here once it writes results.</Empty>
        )}
        {runs && runs.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Condition</th>
                  <th>Model</th>
                  <th>Records</th>
                  <th>Started</th>
                  <th>Finished</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id}>
                    <td>
                      <a className="mono" href={runHref(r.run_id)}>
                        {r.run_id}
                      </a>
                    </td>
                    <td>
                      {r.meta.condition} ({r.meta.condition_alias})
                    </td>
                    <td>
                      {r.meta.provider}/{r.meta.model_id}
                    </td>
                    <td>
                      <span className={`tag ${r.complete ? 'tag-ok' : 'tag-warn'}`}>{completeness(r)}</span>
                    </td>
                    <td>
                      <Time iso={r.meta.started_at} />
                    </td>
                    <td>
                      <Time iso={r.meta.finished_at} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}

import { useEffect, useState, type ReactNode } from 'react'
import { apiGet, errorMessage } from '../shared/api'
import type { RunRowPage, RunSummary } from '../shared/types'
import { Empty, ErrorBox, Loading, PageHeader, Skeleton, Time } from '../shared/ui'
import { completeness, OUTCOMES } from './format'

const PAGE_SIZE = 50

function Records({ id }: { id: string }) {
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<RunRowPage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setPage(null)
    setError(null)
    apiGet<RunRowPage>(`/evaluation/runs/${encodeURIComponent(id)}/records?limit=${PAGE_SIZE}&offset=${offset}`)
      .then((p) => !cancelled && setPage(p))
      .catch((e) => !cancelled && setError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [id, offset])

  return (
    <section className="card" aria-labelledby="rec-h">
      <header>
        <h2 id="rec-h">Per-case records</h2>
      </header>
      {error && (
        <div style={{ padding: 16 }}>
          <ErrorBox>Could not load records: {error}</ErrorBox>
        </div>
      )}
      {!page && !error && <Loading label="Loading records…" />}
      {page && page.items.length === 0 && <Empty title="No records written yet." compact />}
      {page && page.items.length > 0 && (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Outcome</th>
                  <th className="num">Attempts</th>
                  <th>Hidden tests passed</th>
                  <th>Failure reason</th>
                  <th className="num">Tokens in/out</th>
                  <th className="num">Latency (ms)</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((r) => (
                  <tr key={`${r.case_id}.${r.replicate}`}>
                    <td className="mono">{r.case_id}</td>
                    <td>
                      <span
                        className={`tag ${r.outcome === 'TEST_VERIFIED_IN_LAB' ? 'tag-ok' : r.outcome === 'REJECTED' ? 'tag-bad' : 'tag-warn'}`}
                      >
                        {r.outcome}
                      </span>
                    </td>
                    <td className="num">{r.attempts}</td>
                    <td>{r.hidden_passed === null ? '—' : r.hidden_passed ? 'yes' : 'no'}</td>
                    <td>{r.failure_reason ?? '—'}</td>
                    <td className="num">
                      {r.tokens_in} / {r.tokens_out}
                    </td>
                    <td className="num">{r.latency_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </button>
            <button
              className="btn btn-sm"
              disabled={offset + page.items.length >= page.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
            <span className="spacer" />
            <span>
              {page.offset + 1}–{page.offset + page.items.length} of {page.total}
            </span>
          </div>
        </>
      )}
    </section>
  )
}

const fmtNum = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(3))

/** Generic, lossless view of the backend's computed section: nested objects become nested lists. */
function Tree({ v, depth = 0 }: { v: unknown; depth?: number }): ReactNode {
  if (v === null || v === undefined) return <span className="muted">—</span>
  if (typeof v === 'number') return <>{fmtNum(v)}</>
  if (typeof v === 'string' || typeof v === 'boolean') return <>{String(v)}</>
  if (Array.isArray(v)) return <code>{JSON.stringify(v)}</code>
  if (typeof v === 'object') {
    if (depth >= 2) return <code>{JSON.stringify(v)}</code>
    return (
      <dl className="kv" style={depth ? { marginLeft: 8 } : undefined}>
        {Object.entries(v as Record<string, unknown>).map(([k, x]) => (
          <div className="kvrow" key={k}>
            <dt>{k.replace(/_/g, ' ')}</dt>
            <dd>
              <Tree v={x} depth={depth + 1} />
            </dd>
          </div>
        ))}
      </dl>
    )
  }
  return null
}

interface Metrics {
  conditions?: Record<string, { overall?: unknown }>
  not_available?: string[]
}

function ComputedMetrics({ id }: { id: string }) {
  const [rep, setRep] = useState<Metrics | null | undefined>(undefined)
  const [why, setWhy] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    apiGet<Metrics>(`/evaluation/report?run_ids=${encodeURIComponent(id)}`)
      .then((r) => !cancelled && setRep(r))
      .catch((e) => {
        if (cancelled) return
        setWhy(errorMessage(e))
        setRep(null)
      })
    return () => {
      cancelled = true
    }
  }, [id])
  return (
    <section className="card" aria-labelledby="met-h">
      <header>
        <h2 id="met-h">Computed metrics</h2>
      </header>
      {rep === undefined && (
        <div style={{ padding: 16 }}>
          <Skeleton lines={3} />
        </div>
      )}
      {rep === null && (
        <Empty title="Computed metrics are not available for this run.">
          Metrics (Recall@K, MRR, repair rate) come from GET /evaluation/report.
          {why ? ` The API said: ${why}` : ''}
        </Empty>
      )}
      {rep && (
        <div className="pad" style={{ padding: 16 }}>
          {Object.entries(rep.conditions ?? {}).map(([c, sec]) => (
            <div key={c} style={{ marginBottom: 16 }}>
              <h3 className="plain">Condition {c}: overall</h3>
              <Tree v={sec.overall} />
            </div>
          ))}
          {(rep.not_available ?? []).length > 0 && (
            <details>
              <summary>Not available from the stored records</summary>
              <ul>
                {rep.not_available!.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  )
}

export function RunDetail({ id }: { id: string }) {
  const [run, setRun] = useState<RunSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setRun(null)
    setError(null)
    apiGet<RunSummary>(`/evaluation/runs/${encodeURIComponent(id)}`)
      .then((r) => !cancelled && setRun(r))
      .catch((e) => !cancelled && setError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [id, reloadKey])

  if (error)
    return (
      <>
        <PageHeader title="Evaluation run" />
        <ErrorBox onRetry={() => setReloadKey((k) => k + 1)} extra={<a href="#/evaluation">Back to runs</a>}>
          Could not load run: {error}
        </ErrorBox>
      </>
    )
  if (!run)
    return (
      <>
        <PageHeader title="Evaluation run" />
        <div className="card">
          <Loading label="Loading run…" />
        </div>
      </>
    )

  const m = run.meta
  const n = run.n_records
  const extra = Object.keys(run.outcome_counts).filter((k) => !(OUTCOMES as readonly string[]).includes(k))
  const reasons = Object.entries(run.failure_reason_counts ?? {})
  return (
    <>
      <PageHeader
        title={`Run ${run.run_id}`}
        badge={<span className={`tag ${run.complete ? 'tag-ok' : 'tag-warn'}`}>{run.complete ? 'complete' : 'incomplete'}</span>}
        sub={
          <>
            {m.provider}/{m.model_id} · started <Time iso={m.started_at} />
          </>
        }
        actions={
          <a className="btn" href="#/evaluation">
            All runs
          </a>
        }
      />
      <div className="grid-2e">
        <section className="card" aria-labelledby="meta-h">
          <header>
            <h2 id="meta-h">Run details</h2>
          </header>
          <div className="pad" style={{ padding: 16 }}>
            <dl className="kv">
              <dt>Condition</dt>
              <dd>
                {m.condition} ({m.condition_alias})
              </dd>
              <dt>Model</dt>
              <dd>
                {m.provider}/{m.model_id}
              </dd>
              <dt>Temperature</dt>
              <dd>{m.temperature}</dd>
              <dt>Split</dt>
              <dd>{m.split}</dd>
              <dt>Dataset sha256</dt>
              <dd className="mono">{m.dataset_sha256}</dd>
              <dt>Records</dt>
              <dd>{completeness(run)}</dd>
              <dt>Started</dt>
              <dd>{m.started_at ? new Date(m.started_at).toLocaleString() : '—'}</dd>
              <dt>Finished</dt>
              <dd>{m.finished_at ? new Date(m.finished_at).toLocaleString() : '—'}</dd>
            </dl>
          </div>
        </section>
        <div>
          <section className="card" aria-labelledby="oc-h">
            <header>
              <h2 id="oc-h">Outcome counts</h2>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Outcome</th>
                    <th className="num">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {[...OUTCOMES, ...extra].map((o) => (
                    <tr key={o}>
                      <td>{o}</td>
                      <td className="num">
                        {run.outcome_counts[o] ?? 0} / {n}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {reasons.length > 0 && (
            <section className="card" aria-labelledby="fr-h">
              <header>
                <h2 id="fr-h">Failure reasons</h2>
              </header>
              <div className="table-wrap">
                <table>
                  <tbody>
                    {reasons.map(([reason, c]) => (
                      <tr key={reason}>
                        <td>{reason}</td>
                        <td className="num">
                          {c} / {n}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </div>
      <ComputedMetrics id={id} />
      <Records id={id} />
    </>
  )
}

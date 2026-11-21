import { useCallback, useEffect, useState } from 'react'
import { completeness } from '../evaluation/format'
import { useHealth } from '../health/HealthBadge'
import { apiGet, errorMessage } from '../shared/api'
import { incidentHref, runHref } from '../shared/router'
import { StateBadge } from '../shared/StateBadge'
import { ALL_STATES, type Incident, type IncidentPage, type IncidentState, type Report, type RunSummary } from '../shared/types'
import { Empty, ErrorBox, Loading, PageHeader, Skeleton, Time } from '../shared/ui'

interface Counts {
  total: number
  byState: Record<IncidentState, number>
  recent: Incident[]
}

interface ModelInfo {
  source: string
  href: string
  rows: [string, string][]
}

/** Counts come from real totals: one `GET /incidents?state=X&limit=1` per state (no backend aggregate exists). */
async function loadCounts(): Promise<Counts> {
  const [recent, ...per] = await Promise.all([
    apiGet<IncidentPage>('/incidents?limit=8&offset=0'),
    ...ALL_STATES.map((s) => apiGet<IncidentPage>(`/incidents?state=${s}&limit=1`)),
  ])
  const byState = {} as Record<IncidentState, number>
  ALL_STATES.forEach((s, i) => (byState[s] = per[i].total))
  return { total: recent.total, byState, recent: recent.items }
}

function modelFromRun(r: RunSummary): ModelInfo {
  return {
    source: `Latest evaluation run ${r.run_id}`,
    href: runHref(r.run_id),
    rows: [
      ['Model', r.meta.model_id],
      ['Provider', r.meta.provider],
      ['Condition', `${r.meta.condition} (${r.meta.condition_alias})`],
      ['Temperature', String(r.meta.temperature)],
    ],
  }
}

async function modelFromReports(items: Incident[]): Promise<ModelInfo | null> {
  const reports = await Promise.all(
    items.slice(0, 5).map((i) => apiGet<Report>(`/incidents/${i.id}/report`).then((r) => ({ i, r }), () => null)),
  )
  for (const x of reports) {
    const u = x?.r.model_usage
    if (!x || !u) continue
    const pick = (k: string): [string, string][] => (u[k] != null ? [[k, String(u[k])]] : [])
    return {
      source: `Diagnosis report of incident ${x.i.id.slice(0, 8)}`,
      href: incidentHref(x.i.id),
      rows: [...pick('model'), ...pick('provider'), ...pick('tokens_in'), ...pick('tokens_out'), ...pick('latency_ms')].map(
        ([k, v]) => [k.replace(/_/g, ' '), v] as [string, string],
      ),
    }
  }
  return null
}

export function StateBars({ byState }: { byState: Record<IncidentState, number> }) {
  const rows = ALL_STATES.filter((s) => byState[s] > 0)
  const max = Math.max(1, ...rows.map((s) => byState[s]))
  if (rows.length === 0) return <Empty title="No incidents yet" compact />
  const cls = (s: IncidentState) =>
    s === 'REVIEW_PENDING' ? 'pending' : s === 'VERIFIED' || s === 'REVIEWED' || s === 'CLOSED' ? 'good' : s === 'UNVERIFIED' || s === 'INCONCLUSIVE' ? 'attn' : ''
  return (
    <div className="bars" role="list" aria-label="Incidents by state">
      {rows.map((s) => (
        <div className="bar-row" role="listitem" key={s}>
          <a className="bar-name" href={`#/incidents?state=${s}`} title={`Show ${s} incidents`}>
            {s.replace(/_/g, ' ')}
          </a>
          <svg viewBox="0 0 100 12" preserveAspectRatio="none" role="img" aria-label={`${s}: ${byState[s]} of ${max} max`}>
            <rect className="bar-bg" x="0" y="0" width="100" height="12" rx="3" />
            <rect className={`bar-fill ${cls(s)}`} x="0" y="0" width={Math.max(2, (byState[s] / max) * 100)} height="12" rx="3" />
          </svg>
          <span className="count">{byState[s]}</span>
        </div>
      ))}
    </div>
  )
}

export function Dashboard() {
  const [counts, setCounts] = useState<Counts | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [runs, setRuns] = useState<RunSummary[] | null>(null)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [model, setModel] = useState<ModelInfo | null | undefined>(undefined)
  const [reloadKey, setReloadKey] = useState(0)
  const { state: health, health: healthBody } = useHealth()

  const load = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    let cancelled = false
    setError(null)
    setCounts(null)
    loadCounts()
      .then((c) => !cancelled && setCounts(c))
      .catch((e) => !cancelled && setError(errorMessage(e)))
    setRunsError(null)
    setRuns(null)
    apiGet<RunSummary[]>('/evaluation/runs')
      .then((r) => !cancelled && setRuns(r))
      .catch((e) => !cancelled && setRunsError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  // Model info: latest run meta if any run exists; otherwise the newest report that recorded model_usage.
  useEffect(() => {
    if (!counts || runs === null) return
    let cancelled = false
    if (runs.length > 0) setModel(modelFromRun(runs[0]))
    else
      modelFromReports(counts.recent).then((m) => {
        if (!cancelled) setModel(m)
      })
    return () => {
      cancelled = true
    }
  }, [counts, runs])

  const pending = counts?.byState.REVIEW_PENDING ?? 0
  const verified = counts?.byState.VERIFIED ?? 0
  const other = counts ? counts.total - pending - verified : 0

  return (
    <>
      <PageHeader
        title="Dashboard"
        sub="Live counts from the TraceForge API. Nothing here is estimated."
        actions={
          <a className="btn btn-primary" href="#/incidents/new">
            New incident
          </a>
        }
      />
      {error && <ErrorBox onRetry={load}>Could not load incident counts: {error}</ErrorBox>}

      <div className="kpis">
        <Kpi label="Total incidents" value={counts?.total} href="#/incidents" note="all states" loading={!counts && !error} />
        <Kpi label="Awaiting review" value={counts ? pending : undefined} href="#/incidents?state=REVIEW_PENDING" note="state REVIEW_PENDING" loading={!counts && !error} />
        <Kpi label="Verified" value={counts ? verified : undefined} href="#/incidents?state=VERIFIED" note="state VERIFIED" loading={!counts && !error} />
        <Kpi label="Other states" value={counts ? other : undefined} note="in progress, inconclusive, unverified, reviewed, closed" loading={!counts && !error} />
      </div>

      <div className="grid-2">
        <section className="card" aria-labelledby="d-recent">
          <header>
            <h2 id="d-recent">Recent incidents</h2>
            <a href="#/incidents">View all</a>
          </header>
          {!counts && !error && <Loading label="Loading recent incidents…" />}
          {counts && counts.recent.length === 0 && (
            <Empty title="No incidents yet">
              <a href="#/incidents/new">Create the first one</a>
            </Empty>
          )}
          {counts && counts.recent.length > 0 && (
            <ul className="list-rows">
              {counts.recent.map((i) => (
                <li key={i.id}>
                  <div className="grow">
                    <a href={incidentHref(i.id)}>{i.symptom ?? i.id}</a>
                    <span className="cell-sub">
                      {i.service ?? 'no service'} · <span className="mono">{i.id.slice(0, 8)}</span> · <Time iso={i.created_at} />
                    </span>
                  </div>
                  <StateBadge state={i.state} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <div>
          <section className="card" aria-labelledby="d-states">
            <header>
              <h2 id="d-states">Incidents by state</h2>
            </header>
            {counts ? <StateBars byState={counts.byState} /> : <Loading label="Loading state counts…" lines={5} />}
          </section>
          <section className="card" aria-labelledby="d-health">
            <header>
              <h2 id="d-health">System</h2>
            </header>
            <div className="pad" style={{ padding: 16 }}>
              <dl className="kv">
                <dt>API</dt>
                <dd>
                  <span className={`badge badge-${health}`}>{health === 'ok' ? 'ok' : health === 'loading' ? 'checking' : health}</span>
                </dd>
                <dt>Database</dt>
                <dd>{healthBody ? healthBody.db : '—'}</dd>
                <dt>Version</dt>
                <dd>{healthBody ? healthBody.version : '—'}</dd>
              </dl>
            </div>
          </section>
        </div>
      </div>

      <div className="grid-2e">
        <section className="card" aria-labelledby="d-runs">
          <header>
            <h2 id="d-runs">Latest evaluation runs</h2>
            <a href="#/evaluation">All runs</a>
          </header>
          {runsError && <div style={{ padding: 16 }}><ErrorBox onRetry={load}>Could not load runs: {runsError}</ErrorBox></div>}
          {!runs && !runsError && <Loading label="Loading evaluation runs…" />}
          {runs && runs.length === 0 && (
            <Empty title="No evaluation runs yet">Runs appear here once the experiment runner has written results.</Empty>
          )}
          {runs && runs.length > 0 && (
            <ul className="list-rows">
              {runs.slice(0, 4).map((r) => (
                <li key={r.run_id}>
                  <div className="grow">
                    <a href={runHref(r.run_id)}>{r.run_id}</a>
                    <span className="cell-sub">
                      {r.meta.condition} ({r.meta.condition_alias}) · {r.meta.provider}/{r.meta.model_id}
                    </span>
                  </div>
                  <span className={`tag ${r.complete ? 'tag-ok' : 'tag-warn'}`}>{completeness(r)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card" aria-labelledby="d-model">
          <header>
            <h2 id="d-model">Model information</h2>
          </header>
          {model === undefined && !error && (
            <div style={{ padding: 16 }}>
              <Skeleton lines={3} />
            </div>
          )}
          {model === null && (
            <Empty title="No model data recorded yet">
              Shown from the latest evaluation run, or a diagnosis report that recorded model usage. Neither exists yet.
            </Empty>
          )}
          {model && (
            <div className="pad" style={{ padding: 16 }}>
              <dl className="kv">
                {model.rows.map(([k, v]) => (
                  <div className="kvrow" key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
              <p className="muted" style={{ marginTop: 12, marginBottom: 0 }}>
                Source: <a href={model.href}>{model.source}</a>
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  )
}

function Kpi({ label, value, note, href, loading }: { label: string; value?: number; note?: string; href?: string; loading?: boolean }) {
  return (
    <div className="kpi">
      {href ? (
        <a className="label" href={href}>
          {label}
        </a>
      ) : (
        <div className="label">{label}</div>
      )}
      <div className="value" data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, '-')}`}>
        {loading ? <div className="skeleton" style={{ height: 32, width: 56 }} /> : (value ?? '—')}
      </div>
      {note && <div className="note">{note}</div>}
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { apiGet, errorMessage } from '../shared/api'
import { shortId } from '../shared/format'
import { incidentHref } from '../shared/router'
import { StateBadge } from '../shared/StateBadge'
import { ALL_STATES, type IncidentPage, type IncidentState } from '../shared/types'
import { Empty, ErrorBox, Loading, PageHeader, Time } from '../shared/ui'
import { diagnosisOf, verificationOf, type Derived } from './derive'

const PAGE_SIZE = 20

function stateFromHash(): IncidentState | '' {
  const m = /[?&]state=([A-Z_]+)/.exec(window.location.hash)
  return m && (ALL_STATES as string[]).includes(m[1]) ? (m[1] as IncidentState) : ''
}

export function DerivedTag({ d }: { d: Derived }) {
  return (
    <span className={d.tone === 'none' ? 'muted' : `tag tag-${d.tone}`} title={d.title}>
      {d.label}
    </span>
  )
}

export function IncidentList() {
  const [state, setState] = useState<IncidentState | ''>(stateFromHash)
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<IncidentPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const on = () => {
      setState(stateFromHash())
      setOffset(0)
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    let cancelled = false
    setPage(null)
    setError(null)
    const q = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
    if (state) q.set('state', state)
    apiGet<IncidentPage>(`/incidents?${q}`)
      .then((p) => !cancelled && setPage(p))
      .catch((e) => !cancelled && setError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [state, offset, reloadKey])

  const visible = useMemo(() => {
    if (!page) return []
    const q = search.trim().toLowerCase()
    if (!q) return page.items
    return page.items.filter((i) =>
      [i.symptom, i.service, i.id, i.cause_class, i.case_id].some((v) => v?.toLowerCase().includes(q)),
    )
  }, [page, search])

  return (
    <>
      <PageHeader
        title="Incidents"
        sub="Every incident the pipeline has seen, newest first."
        actions={
          <a className="btn btn-primary" href="#/incidents/new">
            New incident
          </a>
        }
      />
      <section className="card" aria-label="Incident list">
        <div className="toolbar">
          <label className="grow">
            <span className="sr-only">Search symptoms</span>
            <input
              type="search"
              placeholder="Search this page by symptom, service, id or category"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <label>
            State
            <select
              value={state}
              onChange={(e) => {
                setState(e.target.value as IncidentState | '')
                setOffset(0)
              }}
            >
              <option value="">All states</option>
              {ALL_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error && (
          <div style={{ padding: 16 }}>
            <ErrorBox onRetry={() => setReloadKey((k) => k + 1)}>Could not load incidents: {error}</ErrorBox>
          </div>
        )}
        {!page && !error && <Loading label="Loading incidents…" lines={6} />}
        {page && page.items.length === 0 && (
          <Empty title={state ? `No incidents in state ${state}.` : 'No incidents yet.'}>
            {state ? (
              <a href="#/incidents" onClick={() => setState('')}>
                Clear the filter
              </a>
            ) : (
              <>
                Create one with <a href="#/incidents/new">New incident</a>.
              </>
            )}
          </Empty>
        )}
        {page && page.items.length > 0 && (
          <>
            {visible.length === 0 ? (
              <Empty title="No incidents on this page match your search." compact />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Incident</th>
                      <th>Symptom</th>
                      <th className="hide-sm">Source</th>
                      <th className="hide-sm">Category</th>
                      <th>Status</th>
                      <th className="hide-sm">Diagnosis</th>
                      <th className="hide-sm">Verification</th>
                      <th className="hide-sm">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((i) => (
                      <tr key={i.id}>
                        <td>
                          <a className="mono" href={incidentHref(i.id)}>
                            {shortId(i.id)}
                          </a>
                          <div className="cell-sub">{i.service ?? '—'}</div>
                        </td>
                        <td>
                          <a className="cell-title" href={incidentHref(i.id)} title={i.symptom ?? undefined}>
                            {i.symptom ? i.symptom.slice(0, 140) : '(no symptom)'}
                          </a>
                          {i.case_id && <div className="cell-sub mono">{i.case_id}</div>}
                        </td>
                        <td className="hide-sm">
                          <span className="tag">{i.source}</span>
                        </td>
                        <td className="hide-sm">{i.cause_class ? <code>{i.cause_class}</code> : <span className="muted">—</span>}</td>
                        <td>
                          <StateBadge state={i.state} />
                        </td>
                        <td className="hide-sm">
                          <DerivedTag d={diagnosisOf(i)} />
                        </td>
                        <td className="hide-sm">
                          <DerivedTag d={verificationOf(i)} />
                        </td>
                        <td className="hide-sm">
                          <Time iso={i.created_at} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
    </>
  )
}

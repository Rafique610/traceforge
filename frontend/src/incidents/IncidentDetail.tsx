import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ReviewPanel } from '../review/ReviewPanel'
import { ApiError, BASE, apiGet, apiPost, errorMessage } from '../shared/api'
import { DiffView, parseDiff } from '../shared/DiffView'
import { exactTime, shortId } from '../shared/format'
import { StateBadge } from '../shared/StateBadge'
import type { AuditEvent, EvidenceItem, Incident, Report } from '../shared/types'
import { CopyButton, Empty, ErrorBox, PageHeader, Skeleton, Time } from '../shared/ui'
import { AuditTimeline } from './AuditTimeline'
import { HitPath, rankedHits } from './HitPath'
import { RatingForm } from '../review/RatingForm'
import { deriveStages } from './pipeline'
import { DevFields } from './DevFields'
import { ProvenanceTag } from './provenance'
import { PipelineStepper } from './PipelineStepper'

/** States that still have work ahead of them, so the page polls. CREATED is idle until investigate exists. */
const POLLING_STATES = new Set([
  'SNAPSHOT_LOCKED',
  'EVIDENCE_COLLECTED',
  'CONTEXT_RETRIEVED',
  'DIAGNOSED',
  'PATCH_PROPOSED',
  'VALIDATING',
  'VERIFIED',
])
export const POLL_MS = 2000
/** Upper bound on investigate polling (about 5 minutes) so a stuck run cannot poll forever. */
const MAX_INVESTIGATE_POLLS = 150

function investigateErrorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 409) return 'This incident is already being investigated, or its current state does not allow a new investigation.'
    if (e.status === 503) return `No model provider is configured, so the investigation could not start. ${e.message}`.trim()
    if (e.status === 404) return 'This incident no longer exists.'
    return `The investigation could not be started (error ${e.status}).`
  }
  return 'Could not reach the server to start the investigation. Check your connection and try again.'
}

interface Data {
  report: Report
  evidence: EvidenceItem[]
  /** null when the audit trail could not be loaded; the stepper then falls back to state + report. */
  events: AuditEvent[] | null
}

function scrollToEvidence(id: string) {
  const el = document.getElementById(`ev-${id}`)
  if (!el) return
  el.closest('details')?.setAttribute('open', '')
  el.querySelector('details')?.setAttribute('open', '')
  el.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  el.classList.add('flash')
  setTimeout(() => el.classList.remove('flash'), 1800)
}

export function EvidenceIds({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="muted">none</span>
  return (
    <span className="ids">
      {ids.map((id) => (
        <button key={id} type="button" className="link mono" onClick={() => scrollToEvidence(id)}>
          {id}
        </button>
      ))}
    </span>
  )
}

function Section({ id, title, children, aside }: { id: string; title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section id={id} className="card section-anchor" aria-labelledby={`${id}-h`}>
      <header>
        <h2 id={`${id}-h`}>{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  )
}

const Pad = ({ children }: { children: ReactNode }) => (
  <div className="pad" style={{ padding: 16 }}>
    {children}
  </div>
)

const val = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v))

function testLabel(t: Record<string, unknown>): { name: string; outcome: string | null } {
  const name = t.name ?? t.nodeid ?? t.test ?? t.id
  const outcome = t.outcome ?? t.status ?? (typeof t.passed === 'boolean' ? (t.passed ? 'passed' : 'failed') : undefined)
  if (name !== undefined) return { name: val(name), outcome: outcome !== undefined ? val(outcome) : null }
  return { name: JSON.stringify(t), outcome: null }
}

const outcomeTone = (o: string) =>
  /^(pass|passed|ok|success|verified)/i.test(o) ? 'tag-ok' : /^(fail|error|reject|unverified)/i.test(o) ? 'tag-bad' : ''

function groupByKind(evidence: EvidenceItem[]): [string, EvidenceItem[]][] {
  const m = new Map<string, EvidenceItem[]>()
  for (const e of evidence) m.set(e.kind, [...(m.get(e.kind) ?? []), e])
  return [...m.entries()]
}

export function IncidentDetail({ id }: { id: string }) {
  const [incident, setIncident] = useState<Incident | null>(null)
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const stateRef = useRef<string | null>(null)
  const [investigating, setInvestigating] = useState(false)
  const [investigateError, setInvestigateError] = useState<string | null>(null)
  const [investigateNote, setInvestigateNote] = useState<string | null>(null)
  const startState = useRef<string | null>(null)
  const statusRef = useRef<HTMLDivElement>(null)

  async function investigate() {
    setInvestigateError(null)
    setInvestigateNote(null)
    startState.current = stateRef.current
    setInvestigating(true)
    try {
      await apiPost(`/incidents/${id}/investigate`, {})
    } catch (e) {
      setInvestigating(false)
      setInvestigateError(investigateErrorText(e))
      return
    }
    setInvestigateNote('Investigation started. This page refreshes until the incident state changes.')
  }

  const load = useCallback(async () => {
    try {
      const [inc, report, evidence, events] = await Promise.all([
        apiGet<Incident>(`/incidents/${id}`),
        apiGet<Report>(`/incidents/${id}/report`),
        apiGet<EvidenceItem[]>(`/incidents/${id}/evidence`),
        apiGet<AuditEvent[]>(`/incidents/${id}/events`).catch(() => null),
      ])
      stateRef.current = inc.state
      setIncident(inc)
      setData({ report, evidence, events })
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  // Poll GET /incidents/{id} while an investigation is in progress; reload everything when the state moves.
  const state = incident?.state
  useEffect(() => {
    if (!state || !POLLING_STATES.has(state)) return
    const t = setInterval(async () => {
      try {
        const inc = await apiGet<Incident>(`/incidents/${id}`)
        if (inc.state !== stateRef.current) await load()
      } catch {
        /* transient; next tick retries */
      }
    }, POLL_MS)
    return () => clearInterval(t)
  }, [id, state, load])

  // After POST /investigate: poll the incident (bounded, stops on unmount) until its state moves.
  useEffect(() => {
    if (!investigating) return
    let polls = 0
    let stopped = false
    const t = setInterval(async () => {
      polls += 1
      try {
        const inc = await apiGet<Incident>(`/incidents/${id}`)
        if (stopped) return
        if (inc.state !== startState.current) {
          clearInterval(t)
          await load()
          if (stopped) return
          setInvestigating(false)
          setInvestigateNote(`Investigation update: the incident is now ${inc.state}.`)
          statusRef.current?.focus()
          return
        }
      } catch {
        /* transient; next tick retries */
      }
      if (polls >= MAX_INVESTIGATE_POLLS && !stopped) {
        clearInterval(t)
        setInvestigating(false)
        setInvestigateNote(null)
        setInvestigateError('The investigation is taking longer than expected. Reload the page to check its current state.')
      }
    }, POLL_MS)
    return () => {
      stopped = true
      clearInterval(t)
    }
  }, [investigating, id, load])

  if (error && !data) {
    return (
      <>
        <PageHeader title="Incident" />
        <ErrorBox onRetry={load} extra={<a href="#/incidents">Back to incidents</a>}>
          Could not load incident: {error}
        </ErrorBox>
      </>
    )
  }
  if (!incident || !data) {
    return (
      <div aria-busy="true">
        <span className="sr-only">Loading incident…</span>
        <PageHeader title="Incident" />
        <div className="card pad" style={{ padding: 16 }}>
          <Skeleton lines={4} block />
        </div>
        <div className="card pad" style={{ padding: 16 }}>
          <Skeleton lines={6} />
        </div>
      </div>
    )
  }

  const { report, evidence, events } = data
  const rc = report.root_cause
  const patch = report.patch
  const withPath = evidence.filter((e) => e.path)
  const polling = POLLING_STATES.has(incident.state)
  const stages = deriveStages(incident.state, events, report)
  const diagEvent = events?.find((e) => e.to_state === 'DIAGNOSED')
  const rationale = typeof diagEvent?.payload.rationale === 'string' ? diagEvent.payload.rationale : null
  const retrieval = events?.find((e) => e.to_state === 'CONTEXT_RETRIEVED')
  const hits = typeof retrieval?.payload.hits === 'number' ? retrieval.payload.hits : null
  const files = patch ? parseDiff(patch.diff).filter((f) => f.lines.length > 0) : []
  const verified = incident.state === 'VERIFIED'
  const unverified = incident.state === 'UNVERIFIED'

  return (
    <article>
      <PageHeader
        title={`Incident ${shortId(incident.id)}`}
        badge={<StateBadge state={incident.state} />}
        sub={
          <>
            {report.header.service ?? 'No service'} · {report.header.origin}
            {report.header.case_id ? ` (${report.header.case_id})` : ''} · created <Time iso={report.header.created_at} />
            {polling && <span className="muted"> · investigation in progress, refreshing every 2 s</span>}
          </>
        }
        actions={
          <>
            <a className="btn" href="#/incidents">
              All incidents
            </a>
            <a className="btn" href={`${BASE}/incidents/${id}/report?format=md`} target="_blank" rel="noreferrer">
              Report (Markdown)
            </a>
            <button type="button" className="btn btn-primary" disabled={investigating || polling} aria-busy={investigating} onClick={investigate}>
              {investigating ? 'Investigating…' : 'Investigate'}
            </button>
          </>
        }
      />
      {error && <ErrorBox>Refresh failed: {error}</ErrorBox>}
      <div ref={statusRef} tabIndex={-1} role="status" aria-live="polite" className="muted">
        {investigateNote}
      </div>
      {investigateError && (
        <p role="alert" className="error">
          {investigateError}
        </p>
      )}

      <section className="card" aria-label="Pipeline">
        <header>
          <h2>Pipeline</h2>
          <span className="muted">from the audit trail{events ? '' : ' (unavailable; derived from state and report)'}</span>
        </header>
        <PipelineStepper
          stages={stages}
          note="A stage with no recorded event is shown as Not run; nothing is assumed to have succeeded."
        />
      </section>

      <nav className="detail-nav" aria-label="Sections">
        {[
          ['sec-summary', 'Summary'],
          ['sec-evidence', 'Evidence'],
          ['sec-retrieval', 'Retrieved context'],
          ['sec-diagnosis', 'Diagnosis'],
          ['sec-patch', 'Patch'],
          ['sec-sandbox', 'Sandbox'],
          ['sec-review', 'Review'],
        ].map(([a, l]) => (
          <a key={a} href={`#/incidents/${id}`} onClick={(e) => { e.preventDefault(); document.getElementById(a)?.scrollIntoView?.({ behavior: 'smooth' }) }}>
            {l}
          </a>
        ))}
      </nav>

      <Section id="sec-summary" title="Summary">
        <Pad>
          {report.symptom ? <p className="symptom-box">{report.symptom}</p> : <p className="muted">No symptom recorded.</p>}
          <p>
            Symptom evidence: <EvidenceIds ids={report.symptom_evidence_ids} />
          </p>
        </Pad>
        <div className="meta-grid" style={{ borderTop: '1px solid var(--border)' }}>
          <Meta k="Service" v={report.header.service ?? '—'} />
          <Meta k="Source" v={`${report.header.origin}${report.header.case_id ? ` (${report.header.case_id})` : ''}`} />
          <Meta k="Base SHA" v={<span className="mono">{report.header.base_sha ?? '—'}</span>} />
          <Meta k="Failure category" v={incident.cause_class ? <code>{incident.cause_class}</code> : '—'} />
          <Meta k="Created" v={exactTime(report.header.created_at)} />
          <Meta k="Updated" v={exactTime(incident.updated_at)} />
        </div>
      </Section>

      <Section id="sec-evidence" title={`Evidence (${evidence.length})`}>
        <div className="notice" style={{ margin: 16 }} role="note">
          Secrets and environment values are redacted by the collector before storage. What you see is the stored text; the SHA-256 of each item is its fingerprint.
        </div>
        {evidence.length === 0 ? (
          <Empty title="No evidence collected yet." compact />
        ) : (
          groupByKind(evidence).map(([kind, items]) => (
            <details className="ev-group" key={kind} open={items.length <= 6}>
              <summary className="ev-sum">
                {kind} <span className="tag">{items.length}</span>
              </summary>
              <ol className="evidence">
                {items.map((e) => (
                  <li key={e.id} id={`ev-${e.id}`}>
                    <div className="row">
                      <span className="mono">{e.id}</span>
                      <span className="muted">
                        {e.service}
                        {e.path ? ` · ${e.path}${e.line != null ? `:${e.line}` : ''}` : ''}
                        {e.ts ? ` · ${exactTime(e.ts)}` : ''}
                      </span>
                      <ProvenanceTag item={e} />
                      <span className="mono muted" title={e.sha256}>
                        sha {e.sha256.slice(0, 8)}
                      </span>
                    </div>
                    <details>
                      <summary>{e.content.slice(0, 160) || '(empty)'}</summary>
                      <pre>{e.content}</pre>
                    </details>
                  </li>
                ))}
              </ol>
            </details>
          ))
        )}
      </Section>

      <Section id="sec-retrieval" title="Retrieved context">
        <Pad>
          {hits != null ? (
            <p>
              <strong>{hits}</strong> retrieval hit{hits === 1 ? '' : 's'} recorded in the audit trail
              {retrieval && (
                <>
                  {' '}
                  (<Time iso={retrieval.created_at} />)
                </>
              )}
              .
            </p>
          ) : (
            <p className="muted">No retrieval event recorded for this incident.</p>
          )}
          {rankedHits(events).length === 0 && (
            <p className="muted" style={{ marginBottom: 0 }}>
              The retrieved snippets themselves are not exposed by the API yet, so only the hit count is shown.
            </p>
          )}
        </Pad>
        {rankedHits(events).length > 0 && <HitPath hits={rankedHits(events)} />}
      </Section>

      <Section id="sec-diagnosis" title="Model diagnosis">
        <Pad>
          <dl className="kv">
            <dt>Status</dt>
            <dd>
              <strong>{rc.status === 'NOT_DIAGNOSED' ? 'Not diagnosed yet' : rc.status}</strong>
            </dd>
            <dt>Cause class</dt>
            <dd>{rc.cause_class ? <code>{rc.cause_class}</code> : '—'}</dd>
            <dt>Target</dt>
            <dd>{rc.target ? <code>{rc.target}</code> : '—'}</dd>
            <dt>Cited evidence</dt>
            <dd>
              <EvidenceIds ids={rc.evidence_ids} />
            </dd>
            {rationale && (
              <>
                <dt>Rationale</dt>
                <dd className="prewrap">{rationale}</dd>
              </>
            )}
          </dl>
          <DevFields payloads={(events ?? []).filter((e) => e.to_state === 'DIAGNOSED' || e.to_state === 'INCONCLUSIVE' || e.to_state === 'REVIEW_PENDING').map((e) => e.payload)} />
          {withPath.length > 0 && (
            <>
              <h3 className="plain" style={{ marginTop: 16 }}>
                Code locations in evidence
              </h3>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {withPath.map((e) => (
                  <li key={e.id}>
                    <code>
                      {e.path}
                      {e.line != null ? `:${e.line}` : ''}
                    </code>{' '}
                    <EvidenceIds ids={[e.id]} />
                  </li>
                ))}
              </ul>
            </>
          )}
          <h3 className="plain" style={{ marginTop: 16 }}>
            Hypotheses
          </h3>
          {report.hypotheses.length === 0 ? (
            <p className="muted">No hypotheses recorded.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {report.hypotheses.map((h, i) => (
                <li key={i} style={{ marginBottom: 8 }}>
                  <code>{h.cause_class ?? 'unclassified'}</code>
                  {h.target && (
                    <>
                      {' '}
                      on <code>{h.target}</code>
                    </>
                  )}
                  <div>
                    Supporting: <EvidenceIds ids={h.supporting_ids} />
                  </div>
                  <div>
                    Contradicting: <EvidenceIds ids={h.contradicting_ids} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <h3 className="plain" style={{ marginTop: 16 }}>
            Model usage
          </h3>
          {report.model_usage ? (
            <dl className="kv">
              {Object.entries(report.model_usage).map(([k, v]) => (
                <div key={k} className="kvrow">
                  <dt>{k.replace(/_/g, ' ')}</dt>
                  <dd>{val(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="muted" style={{ marginBottom: 0 }}>No model usage recorded.</p>
          )}
        </Pad>
      </Section>

      <Section id="sec-patch" title="Proposed patch">
        {patch ? (
          <>
            <div className="pad" style={{ padding: '12px 16px' }}>
              <div className="hash-line">
                <span className="muted">patch sha256</span> <span className="mono">{patch.sha256}</span>
                <CopyButton text={patch.sha256} />
                {patch.signature_changed && <span className="tag tag-warn">signature changed</span>}
              </div>
            </div>
            <ul className="filelist" aria-label="Affected files">
              {(files.length > 0 ? files : patch.paths.map((p) => ({ path: p, add: null, del: null }))).map((f) => (
                <li key={f.path}>
                  <span className="path">{f.path}</span>
                  {f.add != null && (
                    <>
                      <span className="plus">+{f.add}</span>
                      <span className="minus">−{f.del}</span>
                    </>
                  )}
                </li>
              ))}
            </ul>
            <DiffView diff={patch.diff} />
            {patch.impact.length > 0 && (
              <details style={{ padding: 16 }}>
                <summary>Impact ({patch.impact.length})</summary>
                <pre>{JSON.stringify(patch.impact, null, 2)}</pre>
              </details>
            )}
          </>
        ) : rc.status === 'RUNTIME_DEPENDENCY' ? (
          <Pad>
            <div className="outcome" data-outcome="runtime_dependency">
              <p>
                <strong>No patch:</strong> runtime dependency <code>{report.outcome.dependency ?? 'unknown'}</code> is failing.
              </p>
              <p>
                Evidence: <EvidenceIds ids={report.outcome.dependency_evidence_ids} />
              </p>
            </div>
          </Pad>
        ) : rc.status === 'INCONCLUSIVE' ? (
          <Pad>
            <div className="outcome" data-outcome="insufficient_evidence">
              <p>
                <strong>Inconclusive:</strong> missing evidence.
              </p>
              {report.outcome.missing_evidence.length === 0 ? (
                <p className="muted">The report lists no specific missing items.</p>
              ) : (
                <ul>
                  {report.outcome.missing_evidence.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              )}
            </div>
          </Pad>
        ) : (
          <Empty title="No patch proposed." compact>
            {stages[3].detail ? <p>Patch generation ended without a patch: {stages[3].detail}.</p> : null}
          </Empty>
        )}
      </Section>

      <Section id="sec-sandbox" title="Sandbox verification">
        {report.validation_runs.length === 0 ? (
          <Empty title="No validation runs yet." compact />
        ) : (
          <div className="pad" style={{ padding: 16 }}>
            {report.validation_runs.map((r) => (
              <div key={`${r.attempt}-${r.suite}`} style={{ marginBottom: 16 }}>
                <p>
                  Attempt {r.attempt} · {r.suite}: <span className={`tag ${outcomeTone(r.outcome)}`}>{r.outcome}</span>{' '}
                  <span className="muted">
                    ({r.passed} passed, {r.failed} failed)
                  </span>
                </p>
                {r.tests.length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {r.tests.map((t, i) => {
                      const l = testLabel(t)
                      return (
                        <li key={i}>
                          <code>{l.name}</code>
                          {l.outcome && (
                            <>
                              : <span className={`tag ${outcomeTone(l.outcome)}`}>{l.outcome}</span>
                            </>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section id="sec-review" title="Human review">
        <ul className="summary-list" aria-label="Review summary">
          <li>
            <span className="q">What failed</span>
            <span className="prewrap">{report.symptom ?? 'No symptom recorded.'}</span>
          </li>
          <li>
            <span className="q">Why the model believes it</span>
            <span>
              {rc.status === 'NOT_DIAGNOSED' ? (
                'No diagnosis yet.'
              ) : (
                <>
                  {rc.status === 'SUPPORTED' ? 'Hypothesis' : rc.status}
                  {rc.cause_class && (
                    <>
                      : <code>{rc.cause_class}</code>
                    </>
                  )}
                  {rc.target && (
                    <>
                      {' '}
                      in <code>{rc.target}</code>
                    </>
                  )}
                  {rationale && <span className="prewrap"> {'— '}{rationale}</span>}
                </>
              )}
            </span>
          </li>
          <li>
            <span className="q">Supporting evidence</span>
            <EvidenceIds ids={rc.evidence_ids} />
          </li>
          <li>
            <span className="q">What changed</span>
            <span>
              {patch
                ? `${patch.paths.length} file(s): ${patch.paths.join(', ')}${files.length ? ` (+${files.reduce((a, f) => a + f.add, 0)} −${files.reduce((a, f) => a + f.del, 0)})` : ''}`
                : 'No patch was proposed.'}
            </span>
          </li>
          <li>
            <span className="q">Did sandbox verification pass</span>
            <span>
              {verified
                ? 'Yes: the incident reached VERIFIED.'
                : unverified
                  ? 'No: the incident is UNVERIFIED.'
                  : 'Not verified: this incident has no passing sandbox result.'}
            </span>
          </li>
          <li>
            <span className="q">What remains uncertain</span>
            <span>
              {report.limitations || 'The report states no limitations.'}
              {report.outcome.missing_evidence.length > 0 && <> Missing evidence: {report.outcome.missing_evidence.join('; ')}.</>}
            </span>
          </li>
        </ul>
        <div style={{ borderTop: '1px solid var(--border)' }}>
          <ReviewPanel incidentId={id} state={incident.state} patchSha256={patch?.sha256 ?? null} review={report.review} onChanged={load} />
        </div>
      </Section>

      <Section id="sec-audit" title={`Audit timeline (${events?.length ?? 0})`}>
        {events ? <AuditTimeline events={events} /> : <Pad><p className="muted">The audit trail could not be loaded.</p></Pad>}
      </Section>

      <Section id="sec-rating" title="Rate this report">
        <RatingForm incidentId={id} />
      </Section>
    </article>
  )
}

function Meta({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  )
}

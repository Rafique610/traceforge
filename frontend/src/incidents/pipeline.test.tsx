import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { AuditEvent, Report } from '../shared/types'
import { deriveStages } from './pipeline'
import { PipelineStepper } from './PipelineStepper'

const T = '2026-01-01T00:00:00Z'
let n = 0
const ev = (to: string, from: string | null, payload: Record<string, unknown> = {}): AuditEvent => ({
  id: ++n, incident_id: 'i1', actor: 'system', event_type: 'transition',
  from_state: from as AuditEvent['from_state'], to_state: to as AuditEvent['to_state'], payload, payload_sha256: 'x', created_at: T,
})

const report = (over: Partial<Report> = {}): Report => ({
  header: { incident_id: 'i1', case_id: null, service: 'api', base_sha: null, origin: 'lab_case', state: 'X', created_at: T },
  symptom: 's', symptom_evidence_ids: [],
  root_cause: { status: 'NOT_DIAGNOSED', cause_class: null, target: null, evidence_ids: [] },
  outcome: { outcome_class: null, dependency: null, dependency_evidence_ids: [], missing_evidence: [] },
  evidence: [], hypotheses: [], patch: null, validation_runs: [], model_usage: null, review: null, limitations: '',
  ...over,
})

const by = (stages: ReturnType<typeof deriveStages>, key: string) => stages.find((s) => s.key === key)!

describe('pipeline stepper honesty', () => {
  const early = [
    ev('CREATED', null),
    ev('SNAPSHOT_LOCKED', 'CREATED'),
    ev('EVIDENCE_COLLECTED', 'SNAPSHOT_LOCKED', { items: 25 }),
    ev('CONTEXT_RETRIEVED', 'EVIDENCE_COLLECTED', { hits: 21 }),
  ]

  it('marks stages that never ran as Not run and never as done', () => {
    const s = deriveStages('CONTEXT_RETRIEVED', early, report())
    expect(by(s, 'evidence')).toMatchObject({ status: 'done', detail: '25 items' })
    expect(by(s, 'retrieval')).toMatchObject({ status: 'done', detail: '21 hits' })
    for (const k of ['diagnosis', 'patch', 'sandbox', 'review']) expect(by(s, k)).toMatchObject({ status: 'idle', label: 'Not run' })
    render(<PipelineStepper stages={s} />)
    expect(screen.getAllByText('Not run')).toHaveLength(4)
  })

  it('reports a diagnosed incident that produced no patch with the recorded reason', () => {
    const events = [
      ...early,
      ev('DIAGNOSED', 'CONTEXT_RETRIEVED', { rationale: 'because' }),
      ev('REVIEW_PENDING', 'DIAGNOSED', { reason: 'malformed_edit', outcome: 'REJECTED' }),
    ]
    const s = deriveStages('REVIEW_PENDING', events, report({ root_cause: { status: 'SUPPORTED', cause_class: 'application_code', target: 't', evidence_ids: [] } }))
    expect(by(s, 'diagnosis').status).toBe('done')
    expect(by(s, 'patch')).toMatchObject({ status: 'warn', label: 'No patch', detail: 'malformed_edit' })
    expect(by(s, 'sandbox')).toMatchObject({ status: 'idle', label: 'Not run' })
    expect(by(s, 'review')).toMatchObject({ status: 'active', label: 'Awaiting review' })
  })

  it('shows INCONCLUSIVE as a warning, not a success', () => {
    const events = [...early, ev('INCONCLUSIVE', 'CONTEXT_RETRIEVED'), ev('REVIEW_PENDING', 'INCONCLUSIVE')]
    const s = deriveStages('REVIEW_PENDING', events, report())
    expect(by(s, 'diagnosis')).toMatchObject({ status: 'warn', label: 'Inconclusive' })
    expect(by(s, 'patch').label).toBe('Not run')
  })

  it('falls back to state + report when the audit trail is unavailable, without inventing timestamps', () => {
    const s = deriveStages('CREATED', null, report())
    expect(s.every((x) => x.status === 'idle' && !x.at)).toBe(true)
    const v = deriveStages('VERIFIED', null, report({ patch: { sha256: 'a', paths: ['x.py'], diff: '', signature_changed: false, impact: [] } }))
    expect(by(v, 'sandbox')).toMatchObject({ status: 'done', label: 'Verified' })
  })

  it('shows approval only when a review row exists', () => {
    const rev = { id: 'r', decision: 'approve', reviewer: 'Ada', patch_sha256: null, comment: null, created_at: T }
    expect(by(deriveStages('REVIEWED', early, report({ review: rev })), 'review')).toMatchObject({ label: 'Approved', detail: 'by Ada' })
  })
})

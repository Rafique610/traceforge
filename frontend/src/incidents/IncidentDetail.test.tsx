import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockRoutes } from '../test-utils'
import { IncidentDetail } from './IncidentDetail'

afterEach(() => vi.unstubAllGlobals())
const SHA = 'b'.repeat(64)
const TS = '2026-01-01T00:00:00Z'

const incident = (state: string) => ({
  id: 'i1', case_id: 'c1', service: 'api', symptom: '500 on /pay', source: 'lab_case', state, cause_class: null,
  base_sha: 'abc123', created_at: TS, updated_at: TS,
})
const baseReport = (over: object = {}) => ({
  header: { incident_id: 'i1', case_id: 'c1', service: 'api', base_sha: 'abc123', origin: 'lab_case', state: 'REVIEW_PENDING', created_at: TS },
  symptom: '500 on /pay',
  symptom_evidence_ids: ['E1'],
  root_cause: { status: 'SUPPORTED', cause_class: 'config', target: 'app/cfg.py', evidence_ids: ['E1'] },
  outcome: { outcome_class: null, dependency: null, dependency_evidence_ids: [], missing_evidence: [] },
  evidence: [],
  hypotheses: [{ cause_class: 'config', target: 'app/cfg.py', supporting_ids: ['E1'], contradicting_ids: [] }],
  patch: {
    sha256: SHA,
    paths: ['app/cfg.py'],
    diff: '--- a/app/cfg.py\n+++ b/app/cfg.py\n@@ -1 +1 @@\n-x\n+y\n',
    signature_changed: false,
    impact: [],
  },
  validation_runs: [{ attempt: 1, suite: 'visible', passed: 3, failed: 0, outcome: 'pass', tests: [] }],
  model_usage: { model: 'm:free', tokens: 12 },
  review: null,
  limitations: 'none',
  ...over,
})
const evidence = [
  { id: 'E1', incident_id: 'i1', kind: 'log', service: 'api', content: 'Traceback boom', sha256: 'x', path: 'app/cfg.py', line: 4, ts: null },
]

function routes(state: string, report: object) {
  mockRoutes({
    'GET /incidents/i1': incident(state),
    'GET /incidents/i1/report': report,
    'GET /incidents/i1/evidence': evidence,
  })
}

describe('IncidentDetail', () => {
  it('renders sections in the engineer reasoning order', async () => {
    routes('REVIEW_PENDING', baseReport())
    render(<IncidentDetail id="i1" />)
    await screen.findByRole('heading', { name: 'Summary' })
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'Pipeline',
      'Summary',
      'Evidence (1)',
      'Retrieved context',
      'Model diagnosis',
      'Proposed patch',
      'Sandbox verification',
      'Human review',
    ])
    expect(screen.getAllByText('Traceback boom').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Investigate' })).toBeDisabled()
    expect(screen.getByLabelText('Unified diff')).toBeInTheDocument()
  })

  it('shows the retrieval-not-exposed note and the patch file list with counts', async () => {
    routes('REVIEW_PENDING', baseReport())
    render(<IncidentDetail id="i1" />)
    expect(await screen.findByText(/retrieved snippets themselves are not exposed by the API yet/)).toBeInTheDocument()
    const files = screen.getByLabelText('Affected files')
    expect(files).toHaveTextContent('app/cfg.py')
    expect(files).toHaveTextContent('+1')
    expect(screen.getByLabelText('Review summary')).toHaveTextContent('Not verified')
  })

  it('shows the runtime_dependency outcome with no patch', async () => {
    routes(
      'REVIEW_PENDING',
      baseReport({
        patch: null,
        validation_runs: [],
        root_cause: { status: 'RUNTIME_DEPENDENCY', cause_class: null, target: null, evidence_ids: ['E1'] },
        outcome: { outcome_class: 'runtime_dependency', dependency: 'redis', dependency_evidence_ids: ['E1'], missing_evidence: [] },
      }),
    )
    render(<IncidentDetail id="i1" />)
    expect(await screen.findByText('No patch:')).toBeInTheDocument()
    expect(screen.getByText('redis')).toBeInTheDocument()
    expect(screen.queryByLabelText('Unified diff')).not.toBeInTheDocument()
    expect(screen.getByText('No validation runs yet.')).toBeInTheDocument()
  })

  it('shows missing evidence for insufficient_evidence', async () => {
    routes(
      'REVIEW_PENDING',
      baseReport({
        patch: null,
        validation_runs: [],
        root_cause: { status: 'INCONCLUSIVE', cause_class: null, target: null, evidence_ids: [] },
        outcome: { outcome_class: 'insufficient_evidence', dependency: null, dependency_evidence_ids: [], missing_evidence: ['db slow-query log'] },
      }),
    )
    render(<IncidentDetail id="i1" />)
    expect(await screen.findByText('Inconclusive:')).toBeInTheDocument()
    expect(screen.getByText('db slow-query log')).toBeInTheDocument()
  })

  it('shows an error state when the incident cannot be loaded', async () => {
    mockRoutes({})
    render(<IncidentDetail id="i1" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load incident')
  })
})

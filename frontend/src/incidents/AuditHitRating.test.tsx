import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FactorialView, PairedTable, type Paired } from '../evaluation/FactorialView'
import { RatingForm } from '../review/RatingForm'
import { parseHash } from '../shared/router'
import type { AuditEvent } from '../shared/types'
import { json, mockRoutes } from '../test-utils'
import { AuditTimeline } from './AuditTimeline'
import { HitPath, rankedHits } from './HitPath'

afterEach(() => vi.unstubAllGlobals())

const ev = (id: number, over: Partial<AuditEvent> = {}): AuditEvent => ({
  id,
  incident_id: 'i1',
  actor: 'system',
  event_type: 'transition',
  from_state: null,
  to_state: 'CREATED',
  payload: {},
  payload_sha256: 'ab'.repeat(32),
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})

describe('AuditTimeline', () => {
  it('lists events oldest first with actor, transition and payload hash', () => {
    render(
      <AuditTimeline
        events={[ev(2, { actor: 'agent', from_state: 'CREATED', to_state: 'DIAGNOSED' }), ev(1)]}
      />,
    )
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('CREATED')
    expect(items[1]).toHaveTextContent('by agent')
    expect(items[1]).toHaveTextContent('CREATED → DIAGNOSED')
    expect(items[1]).toHaveTextContent('abababababab')
  })
  it('shows an empty state', () => {
    render(<AuditTimeline events={[]} />)
    expect(screen.getByText('No audit events')).toBeInTheDocument()
  })
})

describe('HitPath', () => {
  const ranked = [
    { path: 'a/b.py', kind: 'symbol', start_line: 3, end_line: 9, score: 0.8123, reasons: ['traceback frame', 'calls', 'reads config'] },
  ]
  it('renders each hit with its reasons as a path', () => {
    render(<HitPath hits={ranked} />)
    expect(screen.getByText('a/b.py:3-9')).toBeInTheDocument()
    expect(screen.getByLabelText('Why hit 1 was retrieved')).toHaveTextContent('traceback frame → calls → reads config')
    expect(screen.getByText(/score 0.81/)).toBeInTheDocument()
  })
  it('reads ranked hits from the CONTEXT_RETRIEVED event and tolerates their absence', () => {
    expect(rankedHits([ev(1, { to_state: 'CONTEXT_RETRIEVED', payload: { hits: 1, ranked } })])).toEqual(ranked)
    expect(rankedHits([ev(1, { to_state: 'CONTEXT_RETRIEVED', payload: { hits: 3 } })])).toEqual([])
    expect(rankedHits(null)).toEqual([])
  })
  it('explains when nothing was recorded', () => {
    render(<HitPath hits={[]} />)
    expect(screen.getByText('No ranked hits recorded')).toBeInTheDocument()
  })
})

describe('RatingForm', () => {
  it('stays disabled until all four questions and a name are answered, then posts', async () => {
    const fn = mockRoutes({ 'POST /incidents/i1/ratings': { ok: true } })
    render(<RatingForm incidentId="i1" />)
    const save = screen.getByRole('button', { name: 'Save rating' })
    expect(save).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: 'ruhan' } })
    for (const q of ['cause_clear', 'evidence_convincing', 'patch_understandable', 'would_approve']) {
      fireEvent.click(document.querySelector(`input[name="${q}"][value="4"]`)!)
    }
    expect(save).toBeEnabled()
    fireEvent.click(save)
    expect(await screen.findByRole('status')).toHaveTextContent('saved')
    const body = JSON.parse((fn.mock.calls[0][1] as RequestInit).body as string)
    expect(body).toMatchObject({ rater: 'ruhan', cause_clear: 4, would_approve: 4, note: null })
  })
  it('shows the server error and keeps the form', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'incident or report not found' }, 404)))
    render(<RatingForm incidentId="i1" />)
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: 'x' } })
    for (const q of ['cause_clear', 'evidence_convincing', 'patch_understandable', 'would_approve']) {
      fireEvent.click(document.querySelector(`input[name="${q}"][value="1"]`)!)
    }
    fireEvent.click(screen.getByRole('button', { name: 'Save rating' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('not found')
  })
})

describe('FactorialView', () => {
  const row: Paired = {
    a: 'L0', b: 'G0', metric: 'verified_repair', n_paired: 4, mean_a: 0.25, mean_b: 0.5, mean_diff: 0.25,
    b_better: 2, b_worse: 1, tied: 1, ci95: null, ci_note: 'n_paired < 10: no CI claimed',
  }
  it('shows differences and never invents a CI when the backend gave none', () => {
    render(<PairedTable rows={[row]} />)
    expect(screen.getByText('L0 → G0')).toBeInTheDocument()
    expect(screen.getByText('n_paired < 10: no CI claimed')).toBeInTheDocument()
    expect(screen.getByText('2 / 1 / 1')).toBeInTheDocument()
  })
  it('shows a CI when present', () => {
    render(<PairedTable rows={[{ ...row, n_paired: 12, ci95: [0.1, 0.4], ci_note: null }]} />)
    expect(screen.getByText('[10.0%, 40.0%]')).toBeInTheDocument()
  })
  it('loads the report for the chosen runs', async () => {
    const fn = mockRoutes({ 'GET /evaluation/report?run_ids=r1&run_ids=r2': { paired: [row] } })
    render(<FactorialView runIds={['r1', 'r2']} />)
    await waitFor(() => expect(screen.getByText('verified_repair')).toBeInTheDocument())
    expect(fn).toHaveBeenCalledTimes(1)
  })
  it('shows an honest empty state when the report has no paired field', async () => {
    mockRoutes({ 'GET /evaluation/report?run_ids=r1&run_ids=r2': {} })
    render(<FactorialView runIds={['r1', 'r2']} />)
    expect(await screen.findByText(/No paired comparison is available/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
  it('shows n/a for absent numeric fields instead of inventing numbers', () => {
    render(<PairedTable rows={[{ a: 'L0', b: 'G0', metric: 'm' } as unknown as Paired]} />)
    expect(screen.getAllByText('n/a').length).toBeGreaterThanOrEqual(4)
  })
  it('routes #/evaluation/compare?runs=a,b', () => {
    expect(parseHash('#/evaluation/compare?runs=a,b')).toEqual({ name: 'eval-compare', runs: ['a', 'b'] })
  })
})

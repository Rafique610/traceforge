import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockRoutes } from '../test-utils'
import { ALL_STATES } from '../shared/types'
import { Dashboard } from './Dashboard'

afterEach(() => vi.unstubAllGlobals())

const TS = '2026-01-01T00:00:00Z'
const inc = (n: number, state: string) => ({
  id: `id-${n}0000000`, case_id: null, service: `svc-${n}`, symptom: `symptom ${n}`, source: 'manual', state,
  cause_class: null, base_sha: null, created_at: TS, updated_at: TS,
})
const page = (items: unknown[], total: number) => ({ items, total, limit: 8, offset: 0 })

const COUNTS: Record<string, number> = { REVIEW_PENDING: 3, VERIFIED: 1, CREATED: 2 }

function routes(over: Record<string, unknown> = {}) {
  const r: Record<string, unknown> = {
    'GET /incidents?limit=8&offset=0': page([inc(1, 'REVIEW_PENDING'), inc(2, 'VERIFIED')], 6),
    'GET /health': { status: 'ok', db: 'up', version: '0.1.0' },
    'GET /evaluation/runs': [],
    ...over,
  }
  for (const s of ALL_STATES) r[`GET /incidents?state=${s}&limit=1`] = page([], COUNTS[s] ?? 0)
  return mockRoutes(r)
}

const kpi = (id: string) => screen.getByTestId(`kpi-${id}`)

describe('Dashboard', () => {
  it('computes KPIs only from the API totals', async () => {
    routes()
    render(<Dashboard />)
    expect(await screen.findByText('symptom 1')).toBeInTheDocument()
    expect(kpi('total-incidents')).toHaveTextContent('6')
    expect(kpi('awaiting-review')).toHaveTextContent('3')
    expect(kpi('verified')).toHaveTextContent('1')
    expect(kpi('other-states')).toHaveTextContent('2')
  })

  it('draws the state bars from real counts and hides empty states', async () => {
    routes()
    render(<Dashboard />)
    const list = await screen.findByRole('list', { name: 'Incidents by state' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    expect(within(list).getByText('REVIEW PENDING')).toBeInTheDocument()
    expect(within(list).queryByText('CLOSED')).not.toBeInTheDocument()
  })

  it('shows honest empty states when there are no runs and no model usage', async () => {
    routes()
    render(<Dashboard />)
    expect(await screen.findByText('No evaluation runs yet')).toBeInTheDocument()
    expect(await screen.findByText('No model data recorded yet')).toBeInTheDocument()
  })

  it('takes model info and recent runs from the latest evaluation run meta', async () => {
    routes({
      'GET /evaluation/runs': [
        {
          run_id: 'r1',
          meta: { run_id: 'r1', condition: 'G0', condition_alias: 'G1F0', model_id: 'model-x', provider: 'ollama', temperature: 0, started_at: TS, finished_at: null },
          n_records: 3, n_expected: 4, complete: false, outcome_counts: {}, failure_reason_counts: {},
        },
      ],
    })
    render(<Dashboard />)
    expect(await screen.findByText('model-x')).toBeInTheDocument()
    expect(screen.getByText('3/4 (incomplete)')).toBeInTheDocument()
    expect(screen.getByText('Latest evaluation run r1')).toBeInTheDocument()
  })

  it('reads model info from a report when no run exists', async () => {
    routes({
      'GET /incidents/id-10000000/report': { model_usage: { model: 'qwen-test', provider: 'ollama', tokens_in: 12 } },
    })
    render(<Dashboard />)
    expect(await screen.findByText('qwen-test')).toBeInTheDocument()
    expect(screen.getByText(/Diagnosis report of incident id-10000/)).toBeInTheDocument()
  })

  it('shows an error with retry when counts cannot be loaded', async () => {
    mockRoutes({ 'GET /health': { status: 'ok', db: 'up', version: '0.1.0' }, 'GET /evaluation/runs': [] })
    render(<Dashboard />)
    expect(await screen.findByText(/Could not load incident counts/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

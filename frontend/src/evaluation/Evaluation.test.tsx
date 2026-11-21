import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseHash } from '../shared/router'
import { json, mockRoutes } from '../test-utils'
import { RunDetail } from './RunDetail'
import { RunList } from './RunList'

afterEach(() => vi.unstubAllGlobals())

const meta = {
  run_id: 'r1',
  split: 'dev',
  dataset_sha256: 'ab'.repeat(32),
  condition: 'G0',
  condition_alias: 'G1F0',
  condition_sha256: 'cd'.repeat(32),
  model_id: 'model-x',
  provider: 'ollama',
  temperature: 0,
  prompt_hash: 'ef'.repeat(32),
  git_sha: 'abc',
  replicates: 1,
  n_cases: 4,
  n_expected: 4,
  started_at: '2026-01-01T00:00:00Z',
  finished_at: null,
}
const run = {
  run_id: 'r1',
  meta,
  n_records: 3,
  n_expected: 4,
  complete: false,
  outcome_counts: { UNVERIFIED: 2, NO_PATCH: 1 },
  failure_reason_counts: { 'llm timeout': 2 },
}
const row = {
  case_id: 'case-1',
  replicate: 0,
  outcome: 'UNVERIFIED',
  attempts: 3,
  hidden_passed: null,
  failure_reason: 'llm timeout',
  tokens_in: 10,
  tokens_out: 5,
  latency_ms: 1234,
}

describe('evaluation pages', () => {
  it('parses routes', () => {
    expect(parseHash('#/evaluation')).toEqual({ name: 'eval-list' })
    expect(parseHash('#/evaluation/r1')).toEqual({ name: 'eval-detail', id: 'r1' })
  })

  it('lists runs with alias and completeness', async () => {
    mockRoutes({ 'GET /evaluation/runs': [run] })
    render(<RunList />)
    expect(await screen.findByText('G0 (G1F0)')).toBeInTheDocument()
    expect(screen.getByText('3/4 (incomplete)')).toBeInTheDocument()
  })

  it('shows empty and error states', async () => {
    mockRoutes({ 'GET /evaluation/runs': [] })
    const { unmount } = render(<RunList />)
    expect(await screen.findByText(/No evaluation runs found/)).toBeInTheDocument()
    unmount()
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'boom' }, 500)))
    render(<RunList />)
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })

  it('renders detail with outcome denominators, failure reasons and per-case rows', async () => {
    mockRoutes({
      'GET /evaluation/runs/r1': run,
      'GET /evaluation/runs/r1/records?limit=50&offset=0': { items: [row], total: 1, limit: 50, offset: 0 },
    })
    render(<RunDetail id="r1" />)
    expect((await screen.findAllByText('2 / 3', { selector: 'td' })).length).toBe(2)
    expect(screen.getAllByText('0 / 3', { selector: 'td' })).toHaveLength(2)
    expect(await screen.findByText('case-1')).toBeInTheDocument()
    expect(screen.getByText('1234')).toBeInTheDocument()
    expect(screen.getAllByText('llm timeout').length).toBeGreaterThan(1)
    expect(await screen.findByText('Computed metrics are not available for this run.')).toBeInTheDocument()
  })

  it('shows computed metrics from /evaluation/report when available', async () => {
    mockRoutes({
      'GET /evaluation/runs/r1': run,
      'GET /evaluation/runs/r1/records?limit=50&offset=0': { items: [], total: 0, limit: 50, offset: 0 },
      'GET /evaluation/report?run_ids=r1': {
        conditions: { G0: { overall: { repair_rate: 0.25 } } },
        not_available: ['cache_hit_rate is undefined'],
      },
    })
    render(<RunDetail id="r1" />)
    expect(await screen.findByText('Condition G0: overall')).toBeInTheDocument()
    expect(screen.getByText('0.250')).toBeInTheDocument()
    expect(screen.getByText('cache_hit_rate is undefined')).toBeInTheDocument()
  })

  it('shows an error for an unknown run', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'run not found' }, 404)))
    render(<RunDetail id="nope" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('run not found')
  })
})

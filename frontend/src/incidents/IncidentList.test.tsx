import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { json, mockRoutes } from '../test-utils'
import { IncidentList } from './IncidentList'

afterEach(() => vi.unstubAllGlobals())

const inc = (n: number, state = 'REVIEW_PENDING') => ({
  id: `id-${n}`,
  case_id: null,
  service: `svc-${n}`,
  symptom: `symptom ${n}`,
  source: 'manual',
  state,
  cause_class: 'config',
  base_sha: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})

describe('IncidentList', () => {
  it('renders rows from the API', async () => {
    mockRoutes({ 'GET /incidents?limit=20&offset=0': { items: [inc(1), inc(2)], total: 2, limit: 20, offset: 0 } })
    render(<IncidentList />)
    expect(await screen.findByText('symptom 1')).toBeInTheDocument()
    expect(screen.getByText('svc-2')).toBeInTheDocument()
    expect(screen.getByText('1–2 of 2')).toBeInTheDocument()
  })

  it('shows loading then an empty state', async () => {
    mockRoutes({ 'GET /incidents?limit=20&offset=0': { items: [], total: 0, limit: 20, offset: 0 } })
    render(<IncidentList />)
    expect(screen.getByText('Loading incidents…')).toBeInTheDocument()
    expect(await screen.findByText(/No incidents yet/)).toBeInTheDocument()
  })

  it('shows an error with retry', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'db down' }, 500)))
    render(<IncidentList />)
    expect(await screen.findByRole('alert')).toHaveTextContent('db down')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('passes the state filter to the API', async () => {
    const f = mockRoutes({
      'GET /incidents?limit=20&offset=0': { items: [inc(1)], total: 1, limit: 20, offset: 0 },
      'GET /incidents?limit=20&offset=0&state=VERIFIED': { items: [], total: 0, limit: 20, offset: 0 },
    })
    render(<IncidentList />)
    await screen.findByText('symptom 1')
    await userEvent.selectOptions(screen.getByLabelText('State'), 'VERIFIED')
    await waitFor(() => expect(screen.getByText('No incidents in state VERIFIED.')).toBeInTheDocument())
    expect(f).toHaveBeenCalledWith('/api/incidents?limit=20&offset=0&state=VERIFIED')
  })
})

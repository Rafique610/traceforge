import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HealthBadge } from './HealthBadge'

function mockFetch(impl: () => Promise<unknown>) {
  vi.stubGlobal('fetch', vi.fn(impl))
}

const json = (body: unknown, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

afterEach(() => vi.unstubAllGlobals())

describe('HealthBadge', () => {
  it('shows loading while the request is pending', () => {
    mockFetch(() => new Promise(() => {}))
    render(<HealthBadge />)
    expect(screen.getByText('Checking API…')).toBeInTheDocument()
  })

  it('shows ok when status ok and db up', async () => {
    mockFetch(() => json({ status: 'ok', db: 'up', version: '0.1.0' }))
    render(<HealthBadge />)
    expect(await screen.findByText('API ok')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/health')
  })

  it('shows degraded when db is down', async () => {
    mockFetch(() => json({ status: 'degraded', db: 'down', version: '0.1.0' }))
    render(<HealthBadge />)
    expect(await screen.findByText('API degraded')).toBeInTheDocument()
  })

  it('shows unreachable on network error', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')))
    render(<HealthBadge />)
    expect(await screen.findByText('API unreachable')).toBeInTheDocument()
  })

  it('shows unreachable on non-2xx', async () => {
    mockFetch(() => json({}, 502))
    render(<HealthBadge />)
    expect(await screen.findByText('API unreachable')).toBeInTheDocument()
  })
})

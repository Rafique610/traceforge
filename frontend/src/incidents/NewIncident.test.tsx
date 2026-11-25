import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { json } from '../test-utils'
import { GitHubForm, LabCaseForm, NewIncident } from './NewIncident'
import { validateGitHubUrl } from './validate'

afterEach(() => vi.unstubAllGlobals())

describe('Lab bug form', () => {
  it('lists the server lab bugs and creates a lab-case incident', async () => {
    const created = { id: 'n1', case_id: 'shop_api-017', service: 'shop_api' }
    const f = vi.fn((_url: string, init?: RequestInit) =>
      init?.method === 'POST'
        ? json(created, 201)
        : json({ configured: true, cases: [
            { case_id: 'shop_api-002', service: 'shop_api' },
            { case_id: 'shop_api-017', service: 'shop_api' },
          ] }),
    )
    vi.stubGlobal('fetch', f)
    const onCreated = vi.fn()
    render(<NewIncident onCreated={onCreated} />)
    const select = await screen.findByLabelText('Lab bug')
    await screen.findByRole('option', { name: 'shop_api-017 (shop_api)' })
    await userEvent.selectOptions(select, 'shop_api-017')
    await userEvent.click(screen.getByRole('button', { name: 'Create incident' }))
    const post = f.mock.calls.find(([, init]) => (init as RequestInit)?.method === 'POST')!
    expect(post[0]).toBe('/api/incidents')
    expect(JSON.parse((post[1] as RequestInit).body as string)).toEqual({ case_id: 'shop_api-017', service: 'shop_api' })
    expect(onCreated).toHaveBeenCalledWith(created)
  })

  it('explains an empty list instead of offering a dead button', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ configured: false, cases: [] })))
    render(<LabCaseForm onCreated={() => {}} />)
    expect(await screen.findByText(/No dataset manifest is configured/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create incident' })).toBeDisabled()
  })
})

describe('GitHub form validation', () => {
  it('validates URLs', () => {
    expect(validateGitHubUrl('')).toMatch(/Enter/)
    expect(validateGitHubUrl('http://example.com/x')).toMatch(/Use a URL/)
    expect(validateGitHubUrl('https://github.com/o/r/issues/12')).toBeNull()
  })

  it('blocks submit on an invalid URL without calling the API', async () => {
    const f = vi.fn()
    vi.stubGlobal('fetch', f)
    render(<GitHubForm onCreated={() => {}} />)
    await userEvent.type(screen.getByLabelText('GitHub issue URL'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Create from GitHub' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Use a URL like')
    expect(f).not.toHaveBeenCalled()
  })

  it('posts a valid URL and surfaces server errors', async () => {
    const f = vi.fn(() => json({ detail: 'GitHub rate limit' }, 429))
    vi.stubGlobal('fetch', f)
    render(<GitHubForm onCreated={() => {}} />)
    await userEvent.type(screen.getByLabelText('GitHub issue URL'), 'https://github.com/o/r/issues/1')
    await userEvent.click(screen.getByRole('button', { name: 'Create from GitHub' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('GitHub rate limit')
    expect(f).toHaveBeenCalledWith('/api/incidents/from-github', expect.objectContaining({ method: 'POST' }))
  })
})

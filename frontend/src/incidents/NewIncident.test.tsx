import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { json } from '../test-utils'
import { GitHubForm } from './NewIncident'
import { validateGitHubUrl } from './validate'

afterEach(() => vi.unstubAllGlobals())

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

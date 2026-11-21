import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { json } from '../test-utils'
import { ReviewPanel } from './ReviewPanel'

afterEach(() => vi.unstubAllGlobals())
const SHA = 'a'.repeat(64)
const TS = '2026-01-01T00:00:00Z'

function setup(over: Partial<Parameters<typeof ReviewPanel>[0]> = {}) {
  const onChanged = vi.fn()
  render(
    <ReviewPanel incidentId="i1" state="REVIEW_PENDING" patchSha256={SHA} review={null} onChanged={onChanged} {...over} />,
  )
  return onChanged
}

const bodyOf = (f: ReturnType<typeof vi.fn>) =>
  JSON.parse((f.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)

describe('ReviewPanel', () => {
  it('requires a reviewer name', async () => {
    const f = vi.fn()
    vi.stubGlobal('fetch', f)
    setup()
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Reviewer name is required')
    expect(f).not.toHaveBeenCalled()
  })

  it('posts decision, reviewer, comment and displayed patch hash, then shows the stored decision', async () => {
    const f = vi.fn(() =>
      json(
        { id: 'r1', incident_id: 'i1', patch_sha256: SHA, decision: 'approve', reviewer: 'Ada', comment: 'ok', created_at: TS },
        201,
      ),
    )
    vi.stubGlobal('fetch', f)
    const onChanged = setup()
    await userEvent.type(screen.getByLabelText('Reviewer name'), 'Ada')
    await userEvent.type(screen.getByLabelText('Comment (optional)'), 'ok')
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm approve' }))
    expect(await screen.findByText('Approved')).toBeInTheDocument()
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe('/api/incidents/i1/review')
    expect(bodyOf(f)).toEqual({ decision: 'approve', reviewer: 'Ada', patch_sha256: SHA, comment: 'ok' })
    expect(onChanged).toHaveBeenCalled()
  })

  it('shows the patch-changed message on 409 and asks the page to reload', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'patch hash mismatch' }, 409)))
    const onChanged = setup()
    await userEvent.type(screen.getByLabelText('Reviewer name'), 'Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm reject' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('the patch changed since you loaded it')
    expect(alert).toHaveTextContent('patch hash mismatch')
    expect(onChanged).toHaveBeenCalled()
    expect(screen.queryByText('Rejected')).not.toBeInTheDocument()
  })

  it('shows the server message on 422', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'patch_sha256 required' }, 422)))
    setup()
    await userEvent.type(screen.getByLabelText('Reviewer name'), 'Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm approve' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('patch_sha256 required')
  })

  it('disables decisions outside REVIEW_PENDING', () => {
    setup({ state: 'VALIDATING' })
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
  })

  it('omits patch_sha256 for no-patch outcomes', async () => {
    const f = vi.fn(() =>
      json({ id: 'r', incident_id: 'i1', patch_sha256: null, decision: 'reject', reviewer: 'A', comment: null, created_at: TS }, 201),
    )
    vi.stubGlobal('fetch', f)
    setup({ patchSha256: null })
    await userEvent.type(screen.getByLabelText('Reviewer name'), 'A')
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm reject' }))
    await screen.findByText('Rejected')
    expect(bodyOf(f)).toEqual({ decision: 'reject', reviewer: 'A' })
  })

  it('needs an explicit confirmation step: nothing is sent until Confirm, and Cancel sends nothing', async () => {
    const f = vi.fn()
    vi.stubGlobal('fetch', f)
    setup()
    await userEvent.type(screen.getByLabelText('Reviewer name'), 'Ada')
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(screen.getByRole('group', { name: 'Confirm decision' })).toHaveTextContent('Approve as Ada?')
    expect(f).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Approve' })).toBeEnabled()
    expect(f).not.toHaveBeenCalled()
  })

  it('states that nothing is deployed automatically', () => {
    setup()
    expect(screen.getByRole('note')).toHaveTextContent('Nothing is deployed automatically')
  })
})

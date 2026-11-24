import { useEffect, useRef, useState } from 'react'
import { ApiError, apiPost, errorMessage } from '../shared/api'
import { exactTime } from '../shared/format'
import type { ReviewCreate, ReviewOut, ReviewView } from '../shared/types'
import { CopyButton } from '../shared/ui'

interface Props {
  incidentId: string
  state: string
  patchSha256: string | null
  review: ReviewView | null
  /** Called after a successful review, and after a 409 so the page can reload fresh data. */
  onChanged: () => void
}

type Decision = 'approve' | 'reject'

export function ReviewPanel({ incidentId, state, patchSha256, review, onChanged }: Props) {
  const [reviewer, setReviewer] = useState('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState<ReviewOut | null>(null)
  const [confirming, setConfirming] = useState<Decision | null>(null)

  const stored = saved ?? review
  const cardRef = useRef<HTMLDivElement>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)
  const approveRef = useRef<HTMLButtonElement>(null)
  const rejectRef = useRef<HTMLButtonElement>(null)
  const errorRef = useRef<HTMLInputElement>(null)
  const lastAsked = useRef<Decision>('approve')

  // Move focus to where the user's attention goes after each state change.
  useEffect(() => {
    if (confirming) confirmRef.current?.focus()
  }, [confirming])
  useEffect(() => {
    if (saved) cardRef.current?.focus()
  }, [saved])
  if (stored) {
    return (
      <div className="decision-card" ref={cardRef} tabIndex={-1} role="status" aria-label="Stored decision">
        <p className="big" style={{ margin: 0 }}>
          <strong>{stored.decision === 'approve' ? 'Approved' : 'Rejected'}</strong>{' '}
          <span className="muted" style={{ fontWeight: 400, fontSize: 14 }}>
            by {stored.reviewer} on {exactTime(stored.created_at)}
          </span>
        </p>
        {stored.comment && <p className="prewrap" style={{ margin: 0 }}>{stored.comment}</p>}
        {stored.patch_sha256 && (
          <div className="hash-line">
            <span className="muted">patch sha256</span> <span className="mono">{stored.patch_sha256}</span>
            <CopyButton text={stored.patch_sha256} />
          </div>
        )}
        <p className="muted" style={{ margin: 0 }}>
          Recorded only. TraceForge does not deploy anything automatically; applying the change is a separate, manual step.
        </p>
      </div>
    )
  }

  function ask(decision: Decision) {
    if (!reviewer.trim()) {
      setError('Reviewer name is required.')
      errorRef.current?.focus()
      return
    }
    setError(null)
    lastAsked.current = decision
    setConfirming(decision)
  }

  async function submit(decision: Decision) {
    const body: ReviewCreate = {
      decision,
      reviewer: reviewer.trim(),
      ...(patchSha256 ? { patch_sha256: patchSha256 } : {}),
      ...(comment.trim() ? { comment: comment.trim() } : {}),
    }
    setError(null)
    setBusy(true)
    try {
      setSaved(await apiPost<ReviewOut>(`/incidents/${incidentId}/review`, body))
      onChanged()
    } catch (e) {
      setConfirming(null)
      if (e instanceof ApiError && e.status === 409) {
        setError(
          `Conflict (409): the patch changed since you loaded it, or the incident is not awaiting review. Reload and re-read the diff before deciding. Server said: ${e.message}`,
        )
        onChanged()
      } else if (e instanceof ApiError && e.status === 422) {
        setError(`Rejected by the server (422): ${e.message}`)
      } else {
        setError(errorMessage(e))
      }
    } finally {
      setBusy(false)
    }
  }

  const notReady = state !== 'REVIEW_PENDING'
  return (
    <form onSubmit={(e) => e.preventDefault()} aria-label="Review" noValidate className="pad" style={{ padding: 16 }}>
      <div className="notice" role="note">
        <strong>Nothing is deployed automatically.</strong> Approving records your decision against the exact patch hash below;
        it does not change any running service or repository.
      </div>
      {notReady && (
        <p className="muted">Review opens when the incident is REVIEW_PENDING (currently {state}).</p>
      )}
      <label className="field">
        Reviewer name
        <input
          ref={errorRef}
          value={reviewer}
          aria-required="true"
          aria-invalid={error === 'Reviewer name is required.' ? true : undefined}
          maxLength={80}
          disabled={confirming !== null}
          onChange={(e) => setReviewer(e.target.value)}
          autoComplete="name"
        />
      </label>
      <label className="field">
        Comment (optional)
        <textarea value={comment} maxLength={2000} rows={3} disabled={confirming !== null} onChange={(e) => setComment(e.target.value)} />
      </label>
      <div className="hash-line" style={{ marginBottom: 16 }}>
        {patchSha256 ? (
          <>
            <span className="muted">Deciding on patch sha256</span> <span className="mono">{patchSha256}</span>
            <CopyButton text={patchSha256} />
          </>
        ) : (
          <span className="muted">No patch: this decision covers the diagnosis only.</span>
        )}
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {confirming ? (
        <div className="confirm" role="group" aria-label="Confirm decision">
          <p>
            <strong>
              {confirming === 'approve' ? 'Approve' : 'Reject'} as {reviewer.trim()}?
            </strong>{' '}
            {patchSha256 ? 'The decision is bound to the patch hash shown above.' : 'There is no patch; this covers the diagnosis only.'}{' '}
            This cannot be changed afterwards.
          </p>
          <div className="row">
            <button
              type="button"
              className={confirming === 'approve' ? 'btn btn-primary' : 'btn btn-danger solid'}
              ref={confirmRef}
              disabled={busy}
              onClick={() => submit(confirming)}
            >
              {busy ? 'Saving…' : `Confirm ${confirming}`}
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => {
                setConfirming(null)
                setTimeout(() => (lastAsked.current === 'approve' ? approveRef : rejectRef).current?.focus(), 0)
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="decision-bar">
          <button type="button" ref={approveRef} className="btn btn-primary" disabled={busy || notReady} onClick={() => ask('approve')}>
            Approve
          </button>
          <button type="button" ref={rejectRef} className="btn btn-danger" disabled={busy || notReady} onClick={() => ask('reject')}>
            Reject
          </button>
        </div>
      )}
    </form>
  )
}

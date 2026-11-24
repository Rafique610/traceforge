import { useState } from 'react'
import { apiPost, errorMessage } from '../shared/api'

const QUESTIONS: [string, string][] = [
  ['cause_clear', 'Is the cause clear?'],
  ['evidence_convincing', 'Is the evidence convincing?'],
  ['patch_understandable', 'Is the patch understandable?'],
  ['would_approve', 'Would you approve it?'],
]

/** Usefulness rating of one report: four 1-5 questions and an optional note, saved with the report hash. */
export function RatingForm({ incidentId }: { incidentId: string }) {
  const [rater, setRater] = useState('')
  const [scores, setScores] = useState<Record<string, number>>({})
  const [note, setNote] = useState('')
  const [status, setStatus] = useState<'idle' | 'saving' | 'done'>('idle')
  const [error, setError] = useState<string | null>(null)
  const complete = rater.trim() !== '' && QUESTIONS.every(([k]) => scores[k] >= 1)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!/^[A-Za-z0-9_.@ -]+$/.test(rater.trim())) {
      setError('Name may contain only letters, digits, space and _ . @ -')
      return
    }
    setStatus('saving')
    setError(null)
    try {
      await apiPost(`/incidents/${incidentId}/ratings`, { rater: rater.trim(), ...scores, note: note.trim() || null })
      setStatus('done')
    } catch (err) {
      setError(errorMessage(err))
      setStatus('idle')
    }
  }

  if (status === 'done') return <p role="status">Thank you. Your rating was saved with the hash of this report.</p>
  return (
    <form onSubmit={submit} aria-label="Rate this report" style={{ padding: 16 }}>
      <label>
        Your name <input value={rater} onChange={(e) => setRater(e.target.value)} maxLength={64} />
      </label>
      {QUESTIONS.map(([key, label]) => (
        <fieldset key={key}>
          <legend>{label}</legend>
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} style={{ marginRight: 10 }}>
              <input
                type="radio"
                name={key}
                value={n}
                checked={scores[key] === n}
                onChange={() => setScores({ ...scores, [key]: n })}
              />{' '}
              {n}
            </label>
          ))}
        </fieldset>
      ))}
      <label>
        Note (optional) <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit" className="btn" disabled={!complete || status === 'saving'}>
        Save rating
      </button>
    </form>
  )
}

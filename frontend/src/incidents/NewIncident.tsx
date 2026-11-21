import { useState, type FormEvent } from 'react'
import { apiPost, errorMessage } from '../shared/api'
import { incidentHref } from '../shared/router'
import type { GitHubIntakeOut, Incident } from '../shared/types'
import { PageHeader } from '../shared/ui'
import { validateGitHubUrl } from './validate'

export function GitHubForm({ onCreated }: { onCreated: (i: Incident) => void }) {
  const [url, setUrl] = useState('')
  const [service, setService] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const v = validateGitHubUrl(url)
    if (v) return setError(v)
    setError(null)
    setBusy(true)
    try {
      const out = await apiPost<GitHubIntakeOut>('/incidents/from-github', {
        url: url.trim(),
        ...(service.trim() ? { service: service.trim() } : {}),
      })
      onCreated(out.incident)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate aria-label="Create from GitHub URL">
      <label className="field">
        GitHub issue URL
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/issues/123"
        />
      </label>
      <p className="muted" style={{ marginTop: -8 }}>
        Public issue or pull request URL. The owner must be on the server allowlist.
      </p>
      <label className="field">
        Service (optional)
        <input value={service} onChange={(e) => setService(e.target.value)} />
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <p className="muted">Issue text is imported as untrusted evidence.</p>
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? 'Importing…' : 'Create from GitHub'}
      </button>
    </form>
  )
}

export function ManualForm({ onCreated }: { onCreated: (i: Incident) => void }) {
  const [service, setService] = useState('')
  const [symptom, setSymptom] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!service.trim() || !symptom.trim()) return setError('Service and symptom are both required.')
    setError(null)
    setBusy(true)
    try {
      onCreated(
        await apiPost<Incident>('/incidents', {
          service: service.trim(),
          symptom: symptom.trim(),
          source: 'manual',
        }),
      )
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate aria-label="Create manually">
      <label className="field">
        Service
        <input value={service} onChange={(e) => setService(e.target.value)} placeholder="e.g. shop_api" />
      </label>
      <label className="field">
        Symptom
        <textarea
          value={symptom}
          onChange={(e) => setSymptom(e.target.value)}
          rows={4}
          placeholder="What is failing, and how do you see it?"
        />
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? 'Creating…' : 'Create incident'}
      </button>
    </form>
  )
}

export function NewIncident({ onCreated }: { onCreated: (i: Incident) => void }) {
  const [tab, setTab] = useState<'github' | 'manual'>('github')
  return (
    <section className="card" aria-label="New incident">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'github'} onClick={() => setTab('github')}>
          From GitHub URL
        </button>
        <button role="tab" aria-selected={tab === 'manual'} onClick={() => setTab('manual')}>
          Manual
        </button>
      </div>
      <div className="pad" style={{ padding: 16 }}>
        {tab === 'github' ? <GitHubForm onCreated={onCreated} /> : <ManualForm onCreated={onCreated} />}
        <p className="muted" style={{ marginTop: 16, marginBottom: 0 }}>
          Lab-case intake needs a case-ID listing endpoint, which the API does not expose yet.
        </p>
      </div>
    </section>
  )
}

export function NewIncidentPage() {
  return (
    <div className="page-narrow">
      <PageHeader title="New incident" sub="Report a failing service by hand or import a public GitHub issue." />
      <NewIncident
        onCreated={(i) => {
          window.location.hash = incidentHref(i.id)
        }}
      />
    </div>
  )
}

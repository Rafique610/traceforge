import { useEffect, useState, type FormEvent } from 'react'
import { apiGet, apiPost, errorMessage } from '../shared/api'
import { incidentHref } from '../shared/router'
import type { GitHubIntakeOut, Incident, LabCaseList } from '../shared/types'
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

export function LabCaseForm({ onCreated }: { onCreated: (i: Incident) => void }) {
  const [list, setList] = useState<LabCaseList | null>(null)
  const [caseId, setCaseId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let live = true
    apiGet<LabCaseList>('/lab-cases')
      .then((l) => {
        if (!live) return
        setList(l)
        setCaseId(l.cases[0]?.case_id ?? '')
      })
      .catch((e) => live && setError(`Could not load the lab bugs: ${errorMessage(e)}`))
    return () => {
      live = false
    }
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const c = list?.cases.find((x) => x.case_id === caseId)
    if (!c) return setError('Pick a lab bug first.')
    setError(null)
    setBusy(true)
    try {
      onCreated(await apiPost<Incident>('/incidents', { case_id: c.case_id, service: c.service }))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const empty = list !== null && list.cases.length === 0
  return (
    <form onSubmit={submit} noValidate aria-label="Create from a lab bug">
      <label className="field">
        Lab bug
        <select value={caseId} onChange={(e) => setCaseId(e.target.value)} disabled={!list || empty}>
          {!list && <option value="">Loading…</option>}
          {list?.cases.map((c) => (
            <option key={c.case_id} value={c.case_id}>
              {c.case_id} ({c.service})
            </option>
          ))}
        </select>
      </label>
      <p className="muted" style={{ marginTop: -8 }}>
        A known broken version of the practice shop. The AI is not told what is wrong; it has to find out.
      </p>
      {empty && (
        <p className="muted">
          {list.configured
            ? 'No lab bug has saved evidence on this server yet.'
            : 'No dataset manifest is configured on the server (TRACEFORGE_MANIFEST).'}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button type="submit" className="btn btn-primary" disabled={busy || !caseId}>
        {busy ? 'Creating…' : 'Create incident'}
      </button>
    </form>
  )
}

type Tab = 'lab' | 'github' | 'manual'

export function NewIncident({ onCreated }: { onCreated: (i: Incident) => void }) {
  const [tab, setTab] = useState<Tab>('lab')
  const tabs: [Tab, string][] = [
    ['lab', 'Lab bug'],
    ['github', 'From GitHub URL'],
    ['manual', 'Manual'],
  ]
  return (
    <section className="card" aria-label="New incident">
      <div className="tabs" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>
      <div className="pad" style={{ padding: 16 }}>
        {tab === 'lab' && <LabCaseForm onCreated={onCreated} />}
        {tab === 'github' && <GitHubForm onCreated={onCreated} />}
        {tab === 'manual' && <ManualForm onCreated={onCreated} />}
        {tab !== 'lab' && (
          <p className="muted" style={{ marginTop: 16, marginBottom: 0 }}>
            Only lab bugs can be investigated for now; GitHub and manual incidents are recorded for review.
          </p>
        )}
      </div>
    </section>
  )
}

export function NewIncidentPage() {
  return (
    <div className="page-narrow">
      <PageHeader title="New incident" sub="Start from a lab bug, import a public GitHub issue, or report a failing service by hand." />
      <NewIncident
        onCreated={(i) => {
          window.location.hash = incidentHref(i.id)
        }}
      />
    </div>
  )
}

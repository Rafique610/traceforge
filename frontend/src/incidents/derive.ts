import type { Incident } from '../shared/types'

export interface Derived {
  label: string
  tone: 'ok' | 'warn' | 'bad' | 'info' | 'none'
  title?: string
}

const PRE_DIAGNOSIS = new Set(['CREATED', 'SNAPSHOT_LOCKED', 'EVIDENCE_COLLECTED', 'CONTEXT_RETRIEVED'])
const DIAGNOSED_AT_LEAST = new Set(['DIAGNOSED', 'PATCH_PROPOSED', 'VALIDATING', 'VERIFIED', 'UNVERIFIED'])

/** Diagnosis status from the incident row only (state + cause_class). It never claims more than the row shows. */
export function diagnosisOf(i: Pick<Incident, 'state' | 'cause_class'>): Derived {
  if (PRE_DIAGNOSIS.has(i.state)) return { label: 'Not run', tone: 'none' }
  if (i.state === 'INCONCLUSIVE' || i.cause_class === 'insufficient_evidence') return { label: 'Inconclusive', tone: 'warn' }
  if (i.cause_class === 'runtime_dependency') return { label: 'Runtime dependency', tone: 'info' }
  if (DIAGNOSED_AT_LEAST.has(i.state) || i.cause_class) return { label: 'Diagnosed', tone: 'ok' }
  return { label: 'No root cause', tone: 'warn', title: 'The incident left diagnosis without a recorded cause class' }
}

/** Verification status from state only; later states (REVIEW_PENDING…) do not say, so the detail page must be opened. */
export function verificationOf(i: Pick<Incident, 'state'>): Derived {
  switch (i.state) {
    case 'VERIFIED':
      return { label: 'Verified', tone: 'ok' }
    case 'UNVERIFIED':
      return { label: 'Unverified', tone: 'warn' }
    case 'VALIDATING':
      return { label: 'Running', tone: 'info' }
    case 'REVIEW_PENDING':
    case 'REVIEWED':
    case 'CLOSED':
      return { label: 'See detail', tone: 'none', title: 'The list row does not carry sandbox results; open the incident' }
    default:
      return { label: 'Not run', tone: 'none' }
  }
}

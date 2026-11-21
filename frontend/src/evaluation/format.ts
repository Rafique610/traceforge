import type { RunSummary } from '../shared/types'

export const OUTCOMES = ['TEST_VERIFIED_IN_LAB', 'REJECTED', 'UNVERIFIED', 'NO_PATCH'] as const

export const fmtTime = (s: string | null) => (s ? new Date(s).toLocaleString() : '—')

export const completeness = (r: Pick<RunSummary, 'n_records' | 'n_expected' | 'complete'>) =>
  `${r.n_records}/${r.n_expected ?? '?'} ${r.complete ? '(complete)' : '(incomplete)'}`

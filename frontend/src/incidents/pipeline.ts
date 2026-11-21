import type { AuditEvent, Report } from '../shared/types'

export type StageStatus = 'done' | 'active' | 'warn' | 'fail' | 'idle'

export interface Stage {
  key: 'evidence' | 'retrieval' | 'diagnosis' | 'patch' | 'sandbox' | 'review'
  title: string
  status: StageStatus
  /** Short status text, e.g. "Done", "Not run". */
  label: string
  /** Real detail taken from an audit event payload or the report (counts, reasons, reviewer). */
  detail?: string
  /** ISO timestamp of the audit event that completed the stage, when one exists. */
  at?: string
}

const RANK: Record<string, number> = {
  CREATED: 0,
  SNAPSHOT_LOCKED: 1,
  EVIDENCE_COLLECTED: 2,
  CONTEXT_RETRIEVED: 3,
  DIAGNOSED: 4,
  INCONCLUSIVE: 4,
  PATCH_PROPOSED: 5,
  VALIDATING: 6,
  VERIFIED: 7,
  UNVERIFIED: 7,
  REVIEW_PENDING: 8,
  REVIEWED: 9,
  CLOSED: 10,
}

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' && v ? v : null)

/**
 * Build the six pipeline stages from REAL data only: the audit trail (state transitions with timestamps) when
 * available, otherwise the current incident state plus the report. A stage with no evidence that it ran is "Not run".
 */
export function deriveStages(state: string, events: AuditEvent[] | null, report: Report): Stage[] {
  const hit = (s: string) => events?.find((e) => e.to_state === s)
  const rank = RANK[state] ?? 0
  const fallbackReached = (s: string) => rank >= (RANK[s] ?? 99) && !(s === 'DIAGNOSED' && state === 'INCONCLUSIVE')

  const reached = (s: string) => (events ? !!hit(s) : fallbackReached(s))
  const notRun = (key: Stage['key'], title: string): Stage => ({ key, title, status: 'idle', label: 'Not run' })

  // 1 Evidence collection
  const ev = hit('EVIDENCE_COLLECTED')
  const items = num(ev?.payload.items)
  const evidence: Stage = reached('EVIDENCE_COLLECTED')
    ? { key: 'evidence', title: 'Evidence collection', status: 'done', label: 'Done', at: ev?.created_at, detail: items != null ? `${items} items` : undefined }
    : notRun('evidence', 'Evidence collection')

  // 2 Retrieval
  const ctx = hit('CONTEXT_RETRIEVED')
  const hits = num(ctx?.payload.hits)
  const retrieval: Stage = reached('CONTEXT_RETRIEVED')
    ? { key: 'retrieval', title: 'Retrieval', status: 'done', label: 'Done', at: ctx?.created_at, detail: hits != null ? `${hits} hits` : undefined }
    : notRun('retrieval', 'Retrieval')

  // 3 Diagnosis
  const dg = hit('DIAGNOSED')
  const inc = hit('INCONCLUSIVE')
  let diagnosis: Stage
  if (events ? !!dg : fallbackReached('DIAGNOSED') && (rank < 8 || report.root_cause.status === 'SUPPORTED' || report.root_cause.status === 'RUNTIME_DEPENDENCY'))
    diagnosis = {
      key: 'diagnosis',
      title: 'Diagnosis',
      status: 'done',
      label: report.root_cause.status === 'RUNTIME_DEPENDENCY' ? 'Runtime dependency' : 'Done',
      at: dg?.created_at,
      detail: report.root_cause.cause_class ?? undefined,
    }
  else if (events ? !!inc : state === 'INCONCLUSIVE' || (rank >= 8 && report.root_cause.status === 'INCONCLUSIVE'))
    diagnosis = { key: 'diagnosis', title: 'Diagnosis', status: 'warn', label: 'Inconclusive', at: inc?.created_at }
  else diagnosis = notRun('diagnosis', 'Diagnosis')

  // 4 Patch generation
  const pp = hit('PATCH_PROPOSED')
  const rp = hit('REVIEW_PENDING')
  let patch: Stage
  if (events ? !!pp : report.patch !== null || rank >= 5 && rank < 8)
    patch = { key: 'patch', title: 'Patch generation', status: 'done', label: 'Patch proposed', at: pp?.created_at, detail: report.patch ? `${report.patch.paths.length} file(s)` : undefined }
  else if (diagnosis.status === 'done' && (events ? !!rp : rank >= 8)) {
    const reason = str(rp?.payload.reason)
    patch = {
      key: 'patch',
      title: 'Patch generation',
      status: 'warn',
      label: 'No patch',
      at: rp?.created_at,
      detail: reason ?? (report.root_cause.status === 'RUNTIME_DEPENDENCY' ? 'runtime dependency, nothing to patch' : undefined),
    }
  } else patch = notRun('patch', 'Patch generation')

  // 5 Sandbox verification
  const ver = hit('VERIFIED')
  const unv = hit('UNVERIFIED')
  const val = hit('VALIDATING')
  let sandbox: Stage
  if (events ? !!ver : state === 'VERIFIED')
    sandbox = { key: 'sandbox', title: 'Sandbox verification', status: 'done', label: 'Verified', at: ver?.created_at }
  else if (events ? !!unv : state === 'UNVERIFIED')
    sandbox = { key: 'sandbox', title: 'Sandbox verification', status: 'fail', label: 'Unverified', at: unv?.created_at }
  else if (events ? !!val : state === 'VALIDATING')
    sandbox = { key: 'sandbox', title: 'Sandbox verification', status: 'active', label: 'Running', at: val?.created_at }
  else sandbox = notRun('sandbox', 'Sandbox verification')

  // 6 Human review
  const rev = report.review
  let review: Stage
  if (rev)
    review = {
      key: 'review',
      title: 'Human review',
      status: rev.decision === 'approve' ? 'done' : 'warn',
      label: rev.decision === 'approve' ? 'Approved' : 'Rejected',
      at: rev.created_at,
      detail: `by ${rev.reviewer}`,
    }
  else if (state === 'REVIEW_PENDING')
    review = { key: 'review', title: 'Human review', status: 'active', label: 'Awaiting review', at: rp?.created_at }
  else if (state === 'REVIEWED' || state === 'CLOSED')
    review = { key: 'review', title: 'Human review', status: 'done', label: 'Reviewed', at: hit('REVIEWED')?.created_at }
  else review = notRun('review', 'Human review')

  return [evidence, retrieval, diagnosis, patch, sandbox, review]
}

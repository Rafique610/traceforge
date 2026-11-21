// Hand-written from the Pydantic schemas in backend/traceforge/{incidents,reports,reviews,github}/schemas.py.
// Replace with openapi-typescript output (GET /openapi.json) once the backend is stable.

export type IncidentState =
  | 'CREATED'
  | 'SNAPSHOT_LOCKED'
  | 'EVIDENCE_COLLECTED'
  | 'CONTEXT_RETRIEVED'
  | 'DIAGNOSED'
  | 'INCONCLUSIVE'
  | 'PATCH_PROPOSED'
  | 'VALIDATING'
  | 'VERIFIED'
  | 'UNVERIFIED'
  | 'REVIEW_PENDING'
  | 'REVIEWED'
  | 'CLOSED'

export const ALL_STATES: IncidentState[] = [
  'CREATED',
  'SNAPSHOT_LOCKED',
  'EVIDENCE_COLLECTED',
  'CONTEXT_RETRIEVED',
  'DIAGNOSED',
  'INCONCLUSIVE',
  'PATCH_PROPOSED',
  'VALIDATING',
  'VERIFIED',
  'UNVERIFIED',
  'REVIEW_PENDING',
  'REVIEWED',
  'CLOSED',
]

export type Source = 'lab_case' | 'manual' | 'github'

export interface IncidentCreate {
  case_id?: string | null
  service?: string | null
  symptom?: string | null
  source?: Source | null
}

export interface Incident {
  id: string
  case_id: string | null
  service: string | null
  symptom: string | null
  source: Source
  state: IncidentState
  cause_class: string | null
  base_sha: string | null
  created_at: string
  updated_at: string
}

export interface IncidentPage {
  items: Incident[]
  total: number
  limit: number
  offset: number
}

export interface EvidenceItem {
  id: string
  incident_id: string
  kind: string
  service: string
  content: string
  sha256: string
  path: string | null
  line: number | null
  ts: string | null
}

export interface GitHubIntake {
  url: string
  service?: string | null
}

export interface GitHubIntakeOut {
  incident: Incident
  evidence_id: string
  evidence_sha256: string
  untrusted: boolean
}

export type RootCauseStatus = 'SUPPORTED' | 'INCONCLUSIVE' | 'RUNTIME_DEPENDENCY' | 'NOT_DIAGNOSED'

export interface ReportHeader {
  incident_id: string
  case_id: string | null
  service: string | null
  base_sha: string | null
  origin: string
  state: string
  created_at: string
}

export interface EvidenceRef {
  id: string
  kind: string
  service: string
  path: string | null
  line: number | null
  sha256: string
}

export interface RootCause {
  status: RootCauseStatus
  cause_class: string | null
  target: string | null
  evidence_ids: string[]
}

export interface Hypothesis {
  cause_class: string | null
  target: string | null
  supporting_ids: string[]
  contradicting_ids: string[]
}

export interface PatchView {
  sha256: string
  paths: string[]
  diff: string
  signature_changed: boolean
  impact: Record<string, unknown>[]
}

export interface ValidationView {
  attempt: number
  suite: string
  passed: number
  failed: number
  outcome: string
  tests: Record<string, unknown>[]
}

export interface ReviewView {
  id: string
  decision: string
  reviewer: string
  patch_sha256: string | null
  comment: string | null
  created_at: string
}

export interface OutcomeView {
  outcome_class: string | null
  dependency: string | null
  dependency_evidence_ids: string[]
  missing_evidence: string[]
}

export interface Report {
  header: ReportHeader
  symptom: string | null
  symptom_evidence_ids: string[]
  root_cause: RootCause
  outcome: OutcomeView
  evidence: EvidenceRef[]
  hypotheses: Hypothesis[]
  patch: PatchView | null
  validation_runs: ValidationView[]
  model_usage: Record<string, unknown> | null
  review: ReviewView | null
  limitations: string
}

export interface ReviewCreate {
  decision: 'approve' | 'reject'
  reviewer: string
  patch_sha256?: string | null
  comment?: string | null
}

export interface ReviewOut {
  id: string
  incident_id: string
  patch_sha256: string | null
  decision: 'approve' | 'reject'
  reviewer: string
  comment: string | null
  created_at: string
}

// Evaluation runs: raw counts from backend/traceforge/evaluation/{store,router}.py. No computed metrics.
export type EvalOutcome = 'TEST_VERIFIED_IN_LAB' | 'REJECTED' | 'UNVERIFIED' | 'NO_PATCH'

export interface RunMeta {
  run_id: string
  split: string
  dataset_sha256: string
  condition: string
  condition_alias: string
  condition_sha256: string
  model_id: string
  provider: string
  temperature: number
  prompt_hash: string
  git_sha: string
  replicates: number
  n_cases: number
  n_expected: number
  started_at: string
  finished_at: string | null
}

export interface RunSummary {
  run_id: string
  meta: RunMeta
  n_records: number
  n_expected: number | null
  complete: boolean
  outcome_counts: Record<string, number>
  failure_reason_counts: Record<string, number>
}

export interface RunRow {
  case_id: string
  replicate: number
  outcome: EvalOutcome
  attempts: number
  hidden_passed: boolean | null
  failure_reason: string | null
  tokens_in: number
  tokens_out: number
  latency_ms: number
}

export interface RunRowPage {
  items: RunRow[]
  total: number
  limit: number
  offset: number
}

// Mirrors backend AuditEventOut (incidents/schemas.py): GET /incidents/{id}/events.
export interface AuditEvent {
  id: number
  incident_id: string
  actor: string
  event_type: string
  from_state: IncidentState | null
  to_state: IncidentState | null
  payload: Record<string, unknown>
  payload_sha256: string
  created_at: string
}

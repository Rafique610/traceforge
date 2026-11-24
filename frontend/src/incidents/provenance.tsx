import type { EvidenceItem } from '../shared/types'

/**
 * Provenance label for an evidence item. Uses scope/basis/origin from the API when present; otherwise the same
 * kind/path rule the backend uses (agent/evidence_view.py). A static/declared item says what is written in a file,
 * NOT what the running service uses.
 */
export function provenanceOf(e: Pick<EvidenceItem, 'kind' | 'path' | 'scope' | 'basis' | 'origin'>) {
  let d: [string, string]
  if (e.kind === 'config' && e.path) d = ['static', 'declared']
  else if (e.kind === 'compose') d = ['static', 'declared']
  else d = ['runtime', 'observed']
  return { scope: e.scope || d[0], basis: e.basis || d[1], origin: e.origin ?? null, derived: !(e.scope && e.basis) }
}

export function ProvenanceTag({ item }: { item: EvidenceItem }) {
  const p = provenanceOf(item)
  const title =
    (p.origin ? `${p.origin}. ` : '') +
    (p.scope === 'static'
      ? 'Declared in a source/compose file; not necessarily what the running service uses.'
      : 'Observed in a running service or test run.') +
    (p.derived ? ' (label derived from kind and path)' : '')
  return (
    <span className={`tag ${p.scope === 'static' ? 'tag-warn' : 'tag-info'}`} title={title}>
      {p.scope}/{p.basis}
    </span>
  )
}

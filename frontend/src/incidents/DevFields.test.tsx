import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DevFields } from './DevFields'
import { ProvenanceTag, provenanceOf } from './provenance'

describe('DevFields', () => {
  it('renders nothing when fields are absent', () => {
    const { container } = render(<DevFields payloads={[undefined, { foo: 1 }]} />)
    expect(container).toBeEmptyDOMElement()
  })
  it('shows confidence, symptom, reconciliation and a known reason', () => {
    render(
      <DevFields
        payloads={[{ confidence: 'high', observed_symptom: '500s', reconciliation: 'matches' }, { reason: 'edit_outside_diagnosed_target' }]}
      />,
    )
    expect(screen.getByText('high')).toBeInTheDocument()
    expect(screen.getByText('500s')).toBeInTheDocument()
    expect(screen.getByText('matches')).toBeInTheDocument()
    expect(screen.getByText('edit_outside_diagnosed_target')).toBeInTheDocument()
    expect(screen.getByText(/outside the diagnosed target/)).toBeInTheDocument()
  })
})

describe('provenance', () => {
  it('derives static for config files and runtime for logs; API labels win', () => {
    expect(provenanceOf({ kind: 'config', path: 'a.py' }).scope).toBe('static')
    expect(provenanceOf({ kind: 'log', path: null }).scope).toBe('runtime')
    expect(provenanceOf({ kind: 'log', path: null, scope: 'static', basis: 'declared' }).derived).toBe(false)
  })
  it('renders a tag', () => {
    render(<ProvenanceTag item={{ id: 'E1', incident_id: 'i', kind: 'compose', service: 's', content: '', sha256: 'x', path: null, line: null, ts: null }} />)
    expect(screen.getByText('static/declared')).toBeInTheDocument()
  })
})

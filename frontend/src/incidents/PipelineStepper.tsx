import { Time } from '../shared/ui'
import type { Stage } from './pipeline'

const GLYPH = { done: '✓', fail: '×', warn: '!', active: '…', idle: '' } as const

export function PipelineStepper({ stages, note }: { stages: Stage[]; note?: string }) {
  return (
    <div>
      <ol className="stepper" aria-label="Pipeline progress">
        {stages.map((s, i) => (
          <li key={s.key} className="step" data-status={s.status} data-stage={s.key}>
            <span className="dot" aria-hidden="true">
              {GLYPH[s.status] || i + 1}
            </span>
            <div className="s-title">{s.title}</div>
            <div className="s-status">{s.label}</div>
            {(s.detail || s.at) && (
              <div className="s-meta">
                {s.detail}
                {s.detail && s.at ? ' · ' : ''}
                {s.at && <Time iso={s.at} />}
              </div>
            )}
          </li>
        ))}
      </ol>
      {note && (
        <p className="steps-hint" style={{ padding: '0 16px 12px', margin: 0 }}>
          {note}
        </p>
      )}
    </div>
  )
}

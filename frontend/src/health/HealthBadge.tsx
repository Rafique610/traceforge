import { useEffect, useState } from 'react'
import { apiGet } from '../shared/api'

// Mirrors backend HealthResponse (backend/traceforge/health/schemas.py).
interface Health {
  status: 'ok' | 'degraded'
  db: 'up' | 'down'
  version: string
}

export type HealthState = 'loading' | 'ok' | 'degraded' | 'unreachable'

const LABEL: Record<HealthState, string> = {
  loading: 'Checking API…',
  ok: 'API ok',
  degraded: 'API degraded',
  unreachable: 'API unreachable',
}

export function toState(h: Health): HealthState {
  return h.status === 'ok' && h.db === 'up' ? 'ok' : 'degraded'
}

/** Polls the real /health endpoint; shared by the badge and the dashboard. */
export function useHealth(intervalMs = 0) {
  const [state, setState] = useState<HealthState>('loading')
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    let cancelled = false
    const check = () =>
      apiGet<Health>('/health')
        .then((h) => {
          if (cancelled) return
          setState(toState(h))
          setHealth(h)
        })
        .catch(() => {
          if (cancelled) return
          setState('unreachable')
          setHealth(null)
        })
    check()
    const t = intervalMs > 0 ? setInterval(check, intervalMs) : undefined
    return () => {
      cancelled = true
      if (t) clearInterval(t)
    }
  }, [intervalMs])

  return { state, health }
}

export function HealthBadge() {
  const { state, health } = useHealth(30000)
  const title = health ? `version ${health.version} · db ${health.db}` : undefined
  return (
    <span className={`badge badge-${state}`} data-state={state} title={title} role="status">
      {LABEL[state]}
    </span>
  )
}

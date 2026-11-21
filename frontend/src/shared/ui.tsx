import { useEffect, useRef, useState, type ReactNode } from 'react'
import { exactTime, relativeTime } from './format'

export function Skeleton({ lines = 3, block = false }: { lines?: number; block?: boolean }) {
  return (
    <div aria-hidden="true">
      {block && <div className="skeleton skel-block" />}
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton skel-line" style={{ width: `${95 - ((i * 17) % 40)}%` }} />
      ))}
    </div>
  )
}

/** Loading placeholder with an accessible busy text (tests and screen readers read the label). */
export function Loading({ label, lines = 4 }: { label: string; lines?: number }) {
  return (
    <div aria-busy="true" className="pad" style={{ padding: 16 }}>
      <span className="sr-only">{label}</span>
      <Skeleton lines={lines} />
    </div>
  )
}

export function ErrorBox({ children, onRetry, extra }: { children: ReactNode; onRetry?: () => void; extra?: ReactNode }) {
  return (
    <div role="alert" className="alert">
      <p>{children}</p>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
      {extra}
    </div>
  )
}

export function Empty({ title, children, compact }: { title: string; children?: ReactNode; compact?: boolean }) {
  return (
    <div className={`empty${compact ? ' compact' : ''}`}>
      <strong>{title}</strong>
      {children}
    </div>
  )
}

export function PageHeader({
  title,
  sub,
  actions,
  badge,
}: {
  title: string
  sub?: ReactNode
  actions?: ReactNode
  badge?: ReactNode
}) {
  return (
    <div className="page-head">
      <div className="titles">
        <h1>
          {title}
          {badge}
        </h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Time({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="muted">—</span>
  return (
    <time dateTime={iso} title={exactTime(iso)}>
      {relativeTime(iso)}
    </time>
  )
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [done, setDone] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setDone(false), 1800)
    } catch {
      /* clipboard blocked: leave the button as is */
    }
  }
  return (
    <button type="button" className="btn btn-sm" onClick={copy} aria-label={`${label} to clipboard`}>
      {done ? 'Copied' : label}
    </button>
  )
}

type IconName = 'grid' | 'list' | 'plus' | 'flask' | 'code' | 'pulse' | 'menu' | 'sun' | 'moon' | 'close'
const PATHS: Record<IconName, string> = {
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  plus: 'M12 5v14M5 12h14',
  flask: 'M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9V3',
  code: 'M16 18l6-6-6-6M8 6l-6 6 6 6',
  pulse: 'M3 12h4l3-8 4 16 3-8h4',
  menu: 'M4 6h16M4 12h16M4 18h16',
  sun: 'M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  moon: 'M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z',
  close: 'M6 6l12 12M18 6 6 18',
}
export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  )
}

export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#0f766e" />
      <path d="M7 21l6-8 5 5 7-10" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="25" cy="8" r="2.4" fill="#fff" />
    </svg>
  )
}

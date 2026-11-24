import { useEffect, useState, type ReactNode } from 'react'
import { HealthBadge } from '../health/HealthBadge'
import { BASE } from '../shared/api'
import { useRoute, type Route } from '../shared/router'
import { ThemeToggle } from '../shared/theme'
import { Icon, LogoMark } from '../shared/ui'

type IconName = Parameters<typeof Icon>[0]['name']

interface NavItem {
  href: string
  label: string
  icon: IconName
  active: (r: Route) => boolean
}

const GROUPS: { label: string; items: NavItem[] }[] = [
  { label: 'Overview', items: [{ href: '#/', label: 'Dashboard', icon: 'grid', active: (r) => r.name === 'dashboard' }] },
  {
    label: 'Incidents',
    items: [
      { href: '#/incidents', label: 'All incidents', icon: 'list', active: (r) => r.name === 'list' || r.name === 'detail' },
      { href: '#/incidents/new', label: 'New incident', icon: 'plus', active: (r) => r.name === 'new' },
    ],
  },
  {
    label: 'Evaluation',
    items: [{ href: '#/evaluation', label: 'Runs', icon: 'flask', active: (r) => r.name === 'eval-list' || r.name === 'eval-detail' }],
  },
]

export function breadcrumbs(r: Route): { label: string; href?: string }[] {
  const home = { label: 'TraceForge', href: '#/' }
  switch (r.name) {
    case 'dashboard':
      return [home, { label: 'Dashboard' }]
    case 'list':
      return [home, { label: 'Incidents' }]
    case 'new':
      return [home, { label: 'Incidents', href: '#/incidents' }, { label: 'New incident' }]
    case 'detail':
      return [home, { label: 'Incidents', href: '#/incidents' }, { label: r.id.slice(0, 8) }]
    case 'eval-list':
      return [home, { label: 'Evaluation' }]
    case 'eval-compare':
      return [home, { label: 'Evaluation', href: '#/evaluation' }, { label: 'Compare conditions' }]
    case 'eval-detail':
      return [home, { label: 'Evaluation', href: '#/evaluation' }, { label: r.id }]
    default:
      return [home, { label: 'Not found' }]
  }
}

export function Shell({ children }: { children: ReactNode }) {
  const route = useRoute()
  const [open, setOpen] = useState(false)

  // Close the drawer on navigation and on Escape.
  const routeKey = JSON.stringify(route)
  useEffect(() => setOpen(false), [routeKey])
  useEffect(() => {
    if (!open) return
    const on = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [open])

  const crumbs = breadcrumbs(route)
  return (
    <div className="shell">
      <aside className="sidebar" id="app-sidebar" data-open={open} aria-label="Primary">
        <a className="brand" href="#/" aria-label="TraceForge home">
          <LogoMark />
          <span>TraceForge</span>
        </a>
        <nav aria-label="Main navigation">
          {GROUPS.map((g) => (
            <div className="nav-group" key={g.label}>
              <div className="nav-label">{g.label}</div>
              {g.items.map((i) => (
                <a key={i.href} className="nav-link" href={i.href} aria-current={i.active(route) ? 'page' : undefined}>
                  <Icon name={i.icon} />
                  {i.label}
                </a>
              ))}
            </div>
          ))}
          <div className="nav-group">
            <div className="nav-label">System</div>
            <a className="nav-link" href={`${BASE}/openapi.json`} target="_blank" rel="noreferrer">
              <Icon name="code" />
              OpenAPI schema
            </a>
            <a className="nav-link" href={`${BASE}/health`} target="_blank" rel="noreferrer">
              <Icon name="pulse" />
              Health JSON
            </a>
          </div>
        </nav>
        <div className="side-foot">Review-first diagnosis. Nothing is deployed automatically.</div>
      </aside>
      <div className="scrim" data-open={open} onClick={() => setOpen(false)} aria-hidden="true" />
      <div className="main-col">
        <header className="topbar">
          <button
            type="button"
            className="btn btn-ghost icon-btn menu-btn"
            aria-label={open ? 'Close navigation' : 'Open navigation'}
            aria-expanded={open}
            aria-controls="app-sidebar"
            onClick={() => setOpen((v) => !v)}
          >
            <Icon name={open ? 'close' : 'menu'} />
          </button>
          <nav className="crumbs" aria-label="Breadcrumb">
            <ol>
              {crumbs.map((c, i) => (
                <li key={i} aria-current={i === crumbs.length - 1 ? 'page' : undefined}>
                  {c.href ? <a href={c.href}>{c.label}</a> : c.label}
                </li>
              ))}
            </ol>
          </nav>
          <HealthBadge />
          <ThemeToggle />
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}

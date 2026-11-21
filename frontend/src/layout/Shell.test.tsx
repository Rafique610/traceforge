import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { parseHash } from '../shared/router'
import { ThemeToggle } from '../shared/theme'
import { mockRoutes } from '../test-utils'

beforeEach(() => {
  document.documentElement.removeAttribute('data-theme')
  try {
    localStorage.clear()
  } catch {
    /* ignore */
  }
  window.location.hash = '#/nope'
  mockRoutes({ 'GET /health': { status: 'ok', db: 'up', version: '0.1.0' } })
})
afterEach(() => vi.unstubAllGlobals())

describe('theme toggle', () => {
  it('switches theme, sets data-theme and stores it', async () => {
    render(<ThemeToggle />)
    await userEvent.click(screen.getByRole('button', { name: /Switch to dark theme/ }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem('tf-theme')).toBe('dark')
    await userEvent.click(screen.getByRole('button', { name: /Switch to light theme/ }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('still works when localStorage throws', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    render(<ThemeToggle />)
    await userEvent.click(screen.getByRole('button', { name: /Switch to dark theme/ }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    vi.restoreAllMocks()
  })
})

describe('app shell', () => {
  it('routes the existing hashes', () => {
    expect(parseHash('#/')).toEqual({ name: 'dashboard' })
    expect(parseHash('#/incidents')).toEqual({ name: 'list' })
    expect(parseHash('#/incidents?state=VERIFIED')).toEqual({ name: 'list' })
    expect(parseHash('#/incidents/new')).toEqual({ name: 'new' })
    expect(parseHash('#/incidents/abc')).toEqual({ name: 'detail', id: 'abc' })
    expect(parseHash('#/x')).toEqual({ name: 'not-found' })
  })

  it('renders grouped navigation with an active state, breadcrumbs and a friendly 404', async () => {
    render(<App />)
    expect(await screen.findByText('Page not found')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    for (const l of ['Dashboard', 'All incidents', 'New incident', 'Runs']) expect(nav).toHaveTextContent(l)
    for (const g of ['Overview', 'Incidents', 'Evaluation', 'System']) expect(nav).toHaveTextContent(g)
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Not found')
    expect(await screen.findByText('API ok')).toBeInTheDocument()
  })

  it('collapses the sidebar into a drawer toggled by the menu button', async () => {
    render(<App />)
    const sidebar = document.getElementById('app-sidebar')!
    expect(sidebar).toHaveAttribute('data-open', 'false')
    await userEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(sidebar).toHaveAttribute('data-open', 'true')
    await userEvent.keyboard('{Escape}')
    expect(sidebar).toHaveAttribute('data-open', 'false')
  })

  it('marks the current page in the nav', async () => {
    window.location.hash = '#/incidents/new'
    render(<App />)
    const link = await screen.findByRole('link', { name: 'New incident', current: 'page' })
    expect(link).toHaveAttribute('href', '#/incidents/new')
  })
})

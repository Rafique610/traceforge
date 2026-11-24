import { useEffect, useState } from 'react'

export type Route =
  | { name: 'dashboard' }
  | { name: 'list' }
  | { name: 'new' }
  | { name: 'detail'; id: string }
  | { name: 'eval-list' }
  | { name: 'eval-detail'; id: string }
  | { name: 'eval-compare'; runs: string[] }
  | { name: 'not-found' }

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, '').replace(/[?].*$/, '') || '/'
  if (path === '/') return { name: 'dashboard' }
  if (path === '/incidents') return { name: 'list' }
  if (path === '/incidents/new') return { name: 'new' }
  if (path === '/evaluation') return { name: 'eval-list' }
  if (path === '/evaluation/compare') {
    const q = new URLSearchParams(hash.split('?')[1] ?? '')
    return { name: 'eval-compare', runs: (q.get('runs') ?? '').split(',').filter(Boolean) }
  }
  const e = /^\/evaluation\/([^/]+)$/.exec(path)
  if (e) return { name: 'eval-detail', id: decodeURIComponent(e[1]) }
  const m = /^\/incidents\/([^/]+)$/.exec(path)
  if (m) return { name: 'detail', id: decodeURIComponent(m[1]) }
  return { name: 'not-found' }
}

export function useRoute(): Route {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const on = () => setHash(window.location.hash)
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return parseHash(hash)
}

export const runHref = (id: string) => `#/evaluation/${encodeURIComponent(id)}`
export const incidentHref = (id: string) => `#/incidents/${encodeURIComponent(id)}`

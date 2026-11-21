import { vi } from 'vitest'

export const json = (body: unknown, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

/** Route-table fetch mock: key is "METHOD /path-with-query"; value is a body. */
export function mockRoutes(routes: Record<string, unknown>) {
  const fn = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${url.replace(/^\/api/, '')}`
    const r = routes[key]
    if (r === undefined) return json({ detail: `unmocked ${key}` }, 404)
    return json(r)
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

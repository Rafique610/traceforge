export const BASE = import.meta.env.VITE_API_URL ?? '/api'

/** Error carrying the HTTP status and the server's `detail` message (when present). */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function detailOf(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    const d = body?.detail
    if (typeof d === 'string') return d
    // FastAPI request-validation errors: [{loc, msg, ...}]
    if (Array.isArray(d)) {
      return d
        .map((e: { loc?: unknown[]; msg?: string }) =>
          [e.loc?.filter((p) => p !== 'body').join('.'), e.msg].filter(Boolean).join(': '),
        )
        .join('; ')
    }
  } catch {
    /* body not JSON */
  }
  return fallback
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path)
  if (!res.ok) {
    throw new ApiError(res.status, await detailOf(res, `GET ${path} failed with status ${res.status}`))
  }
  return (await res.json()) as T
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new ApiError(res.status, await detailOf(res, `POST ${path} failed with status ${res.status}`))
  }
  return (await res.json()) as T
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

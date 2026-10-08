import type { FieldPath, FieldValue, Health, SessionView, TurnResult } from './types'

/** Every failure, including network errors, surfaces as an ApiError with the backend's code. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryable: boolean

  constructor(status: number, code: string, message: string, retryable: boolean) {
    super(message)
    this.status = status
    this.code = code
    this.retryable = retryable
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; retryable?: boolean }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the server. Is the backend running?', true)
  }
  if (!res.ok) {
    let body: ErrorEnvelope = {}
    try {
      body = (await res.json()) as ErrorEnvelope
    } catch {
      // Non-JSON error (e.g. proxy failure); fall back to the status code.
    }
    throw new ApiError(
      res.status,
      body.error?.code ?? 'http_error',
      body.error?.message ?? `Request failed (${res.status})`,
      body.error?.retryable ?? res.status >= 500,
    )
  }
  return (await res.json()) as T
}

export const api = {
  health: () => request<Health>('/health'),

  createSession: () => request<SessionView>('/sessions', { method: 'POST' }),

  getSession: (id: string) => request<SessionView>(`/sessions/${encodeURIComponent(id)}`),

  sendMessage: (id: string, content: string, expectedVersion: number) =>
    request<TurnResult>(`/sessions/${encodeURIComponent(id)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, expected_version: expectedVersion }),
    }),

  editField: (id: string, path: FieldPath, value: FieldValue, expectedVersion: number) =>
    request<SessionView>(`/sessions/${encodeURIComponent(id)}/fields`, {
      method: 'PATCH',
      body: JSON.stringify({ path, value, expected_version: expectedVersion }),
    }),

  documentUrl: (id: string) => `/api/sessions/${encodeURIComponent(id)}/document`,
}

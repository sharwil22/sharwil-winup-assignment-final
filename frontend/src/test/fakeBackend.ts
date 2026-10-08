import { vi } from 'vitest'
import type { FieldView, SessionView, TurnResult } from '../api/types'

const LABELS: [FieldView['path'], string][] = [
  ['full_name', 'full name'],
  ['home_address', 'home address'],
  ['covers_worldwide_assets', 'whether the document covers worldwide assets'],
  ['has_children', 'whether you have children'],
  ['children_names', "children's names"],
  ['executor.name', "executor's name"],
  ['executor.relationship', "executor's relationship to you"],
  ['specific_gifts', 'specific gifts'],
  ['additional_wishes', 'additional wishes'],
]

export function emptySession(): SessionView {
  return {
    id: 's1',
    version: 0,
    fields: LABELS.map(([path, label]) => ({
      path,
      label,
      value: null,
      status: 'missing',
      candidate: null,
      note: null,
      source: null,
      source_turn: null,
      evidence: null,
      previous_value: null,
    })),
    state: {},
    messages: [{ role: 'assistant', content: 'Hello! What is your full name?' }],
    document_markdown: '> **FICTIONAL DRAFT — NOT LEGAL ADVICE.**\n\nI, [To be confirmed: full name]',
    progress: { completed: 0, total: 9 },
    is_complete: false,
    focus: 'full_name',
    next_question: 'What is your full name?',
  }
}

export function withName(session: SessionView, name: string, content: string): TurnResult {
  const reply = 'Thanks, I have noted that. What is your home address?'
  return {
    ...session,
    version: session.version + 1,
    fields: session.fields.map((f) =>
      f.path === 'full_name'
        ? { ...f, value: name, status: 'captured', source: 'chat', source_turn: 1, evidence: content }
        : f,
    ),
    messages: [...session.messages, { role: 'user', content }, { role: 'assistant', content: reply }],
    document_markdown: `> **FICTIONAL DRAFT — NOT LEGAL ADVICE.**\n\nI, ${name}`,
    progress: { completed: 1, total: 9 },
    focus: 'home_address',
    reply,
    changes: [
      {
        path: 'full_name',
        label: 'full name',
        old_value: null,
        new_value: name,
        old_status: 'missing',
        new_status: 'captured',
      },
    ],
    rejected_updates: [],
    warnings: [],
  }
}

type Reply = { status: number; body: unknown }
type Handler = (init: RequestInit | undefined) => Reply

/** A tiny routing fake for `fetch`. Queue per-route responses; unqueued routes use defaults. */
export function installFakeBackend(options: { provider?: string; configured?: boolean } = {}) {
  const session = emptySession()
  const queues = new Map<string, Handler[]>()
  const calls: { method: string; path: string; body: unknown }[] = []

  const defaults: Record<string, Handler> = {
    'GET /api/health': () => ({
      status: 200,
      body: { status: 'ok', provider: options.provider ?? 'mock', model_configured: options.configured ?? true },
    }),
    'POST /api/sessions': () => ({ status: 201, body: session }),
    'GET /api/sessions/s1': () => ({ status: 200, body: session }),
  }

  function queue(route: string, ...handlers: Handler[]) {
    queues.set(route, [...(queues.get(route) ?? []), ...handlers])
  }

  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const method = init?.method ?? 'GET'
    const route = `${method} ${url}`
    calls.push({ method, path: url, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const handler = queues.get(route)?.shift() ?? defaults[route]
    if (!handler) return new Response(JSON.stringify({ error: { code: 'not_found', message: route } }), { status: 404 })
    const { status, body } = handler(init)
    return new Response(JSON.stringify(body), { status })
  })

  return { session, queue, calls }
}

export function errorReply(status: number, code: string, message: string, retryable: boolean): Reply {
  return { status, body: { error: { code, message, retryable } } }
}

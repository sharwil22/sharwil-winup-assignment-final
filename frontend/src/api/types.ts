// Mirrors backend/app/api/schemas.py. The backend's OpenAPI at /openapi.json is the source.

export type FieldStatus = 'missing' | 'needs_clarification' | 'captured' | 'not_applicable'

export type FieldPath =
  | 'full_name'
  | 'home_address'
  | 'covers_worldwide_assets'
  | 'has_children'
  | 'children_names'
  | 'executor.name'
  | 'executor.relationship'
  | 'specific_gifts'
  | 'additional_wishes'

export interface Gift {
  item: string
  recipient: string
}

export type FieldValue = string | boolean | string[] | Gift[] | null

export interface FieldView {
  path: FieldPath
  label: string
  value: FieldValue
  status: FieldStatus
  candidate: FieldValue
  note: string | null
  // Provenance of a captured value
  source: 'chat' | 'edit' | null
  source_turn: number | null
  evidence: string | null
  previous_value: FieldValue
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface SessionView {
  id: string
  version: number
  fields: FieldView[]
  state: Record<string, unknown>
  messages: Message[]
  document_markdown: string
  progress: { completed: number; total: number }
  is_complete: boolean
  focus: FieldPath | null
  next_question: string
}

export interface ChangeView {
  path: FieldPath
  label: string
  old_value: FieldValue
  new_value: FieldValue
  old_status: FieldStatus
  new_status: FieldStatus
}

export interface TurnResult extends SessionView {
  reply: string
  changes: ChangeView[]
  rejected_updates: { path: FieldPath; reason: string }[]
  warnings: string[]
}

export interface Health {
  status: 'ok'
  provider: string
  model_configured: boolean
}

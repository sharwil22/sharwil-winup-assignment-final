import { useState, type FormEvent } from 'react'
import type { FieldView, FieldValue } from '../api/types'
import { BOOL_PATHS, fromEditorText, toEditorText } from '../format'

interface Props {
  field: FieldView
  onSave: (value: FieldValue) => Promise<string | null>
  onCancel: () => void
}

const HINTS: Partial<Record<FieldView['path'], string>> = {
  children_names: 'Separate names with commas.',
  specific_gifts: 'One gift per line, as "item to person". Leave empty for none.',
  additional_wishes: 'Leave empty for none.',
}

export function FieldEditor({ field, onSave, onCancel }: Props) {
  const isBool = BOOL_PATHS.includes(field.path)
  const initial = field.value ?? field.candidate
  const [text, setText] = useState(isBool ? '' : toEditorText(field.path, initial))
  const [choice, setChoice] = useState<'' | 'yes' | 'no'>(
    typeof initial === 'boolean' ? (initial ? 'yes' : 'no') : '',
  )
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const multiline = field.path === 'specific_gifts' || field.path === 'additional_wishes'
  const inputId = `edit-${field.path}`

  async function submit(e: FormEvent) {
    e.preventDefault()
    let value: FieldValue
    if (isBool) {
      if (!choice) return setError('Choose yes or no.')
      value = choice === 'yes'
    } else {
      const parsed = fromEditorText(field.path, text)
      if (parsed !== null && typeof parsed === 'object' && 'error' in parsed) {
        return setError(parsed.error)
      }
      value = parsed as FieldValue
    }
    setSaving(true)
    const problem = await onSave(value)
    setSaving(false)
    if (problem) setError(problem)
  }

  return (
    <form className="field-editor" onSubmit={(e) => void submit(e)}>
      <label htmlFor={inputId} className="visually-hidden">
        {field.label}
      </label>
      {isBool ? (
        <select id={inputId} value={choice} onChange={(e) => setChoice(e.target.value as typeof choice)}>
          <option value="">Choose…</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      ) : multiline ? (
        <textarea id={inputId} value={text} rows={3} onChange={(e) => setText(e.target.value)} autoFocus />
      ) : (
        <input id={inputId} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
      )}
      {HINTS[field.path] && <p className="hint">{HINTS[field.path]}</p>}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  )
}

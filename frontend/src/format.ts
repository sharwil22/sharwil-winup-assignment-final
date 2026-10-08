import type { FieldPath, FieldValue, Gift } from './api/types'

export const OPTIONAL_PATHS: FieldPath[] = ['specific_gifts', 'additional_wishes']
export const BOOL_PATHS: FieldPath[] = ['covers_worldwide_assets', 'has_children']

function isGiftList(value: unknown[]): value is Gift[] {
  return value.length > 0 && typeof value[0] === 'object' && value[0] !== null
}

export function formatValue(value: FieldValue): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) {
    if (value.length === 0) return 'None'
    if (isGiftList(value)) return value.map((g) => `${g.item} → ${g.recipient}`).join('; ')
    return (value as string[]).join(', ')
  }
  return value === '' ? 'None' : value
}

/** Text shown in the editor for a value. Gifts are one "item to recipient" per line. */
export function toEditorText(path: FieldPath, value: FieldValue): string {
  if (value === null || value === undefined) return ''
  if (path === 'specific_gifts' && Array.isArray(value)) {
    return (value as Gift[]).map((g) => `${g.item} to ${g.recipient}`).join('\n')
  }
  if (Array.isArray(value)) return (value as string[]).join(', ')
  return String(value)
}

/** Parse editor text back into the value the API expects. Returns an error message if invalid. */
export function fromEditorText(path: FieldPath, text: string): FieldValue | { error: string } {
  const trimmed = text.trim()
  if (path === 'children_names') {
    const names = trimmed.split(',').map((n) => n.trim()).filter(Boolean)
    return names.length ? names : { error: 'Enter at least one name, separated by commas.' }
  }
  if (path === 'specific_gifts') {
    const gifts: Gift[] = []
    for (const line of trimmed.split('\n').map((l) => l.trim()).filter(Boolean)) {
      const match = /^(.+?)\s+to\s+(.+)$/i.exec(line)
      if (!match) return { error: `Write each gift as "item to person": "${line}"` }
      gifts.push({ item: match[1].trim(), recipient: match[2].trim() })
    }
    return gifts // empty list = "no specific gifts"
  }
  return trimmed // empty additional wishes = "none"; empty required text is rejected by the API
}

import { describe, expect, it } from 'vitest'
import { formatValue, fromEditorText, toEditorText } from './format'

describe('formatValue', () => {
  it('formats each kind of value', () => {
    expect(formatValue(null)).toBe('—')
    expect(formatValue(true)).toBe('Yes')
    expect(formatValue(false)).toBe('No')
    expect(formatValue('')).toBe('None')
    expect(formatValue([])).toBe('None')
    expect(formatValue(['Tom', 'Ann'])).toBe('Tom, Ann')
    expect(formatValue([{ item: 'car', recipient: 'Tom' }])).toBe('car → Tom')
  })
})

describe('editor text', () => {
  it('round-trips gifts as one "item to person" per line', () => {
    const gifts = [
      { item: 'my car', recipient: 'Tom' },
      { item: 'piano', recipient: 'Ann Smith' },
    ]
    const text = toEditorText('specific_gifts', gifts)
    expect(text).toBe('my car to Tom\npiano to Ann Smith')
    expect(fromEditorText('specific_gifts', text)).toEqual(gifts)
  })

  it('treats an empty gift list as "none" and rejects unparseable lines', () => {
    expect(fromEditorText('specific_gifts', '  ')).toEqual([])
    expect(fromEditorText('specific_gifts', 'my car')).toEqual({
      error: 'Write each gift as "item to person": "my car"',
    })
  })

  it('splits children names on commas and requires at least one', () => {
    expect(fromEditorText('children_names', 'Tom, Ann ,')).toEqual(['Tom', 'Ann'])
    expect(fromEditorText('children_names', ' ')).toEqual({
      error: 'Enter at least one name, separated by commas.',
    })
  })
})

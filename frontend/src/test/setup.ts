import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Node 25+ defines an experimental global `localStorage` that shadows jsdom's and throws
// without --localstorage-file. Tests get a simple in-memory Storage instead.
class MemoryStorage implements Storage {
  private data = new Map<string, string>()
  get length() {
    return this.data.size
  }
  clear() {
    this.data.clear()
  }
  getItem(key: string) {
    return this.data.get(key) ?? null
  }
  key(index: number) {
    return [...this.data.keys()][index] ?? null
  }
  removeItem(key: string) {
    this.data.delete(key)
  }
  setItem(key: string, value: string) {
    this.data.set(key, String(value))
  }
}

Object.defineProperty(globalThis, 'localStorage', { value: new MemoryStorage(), configurable: true })

afterEach(() => cleanup())

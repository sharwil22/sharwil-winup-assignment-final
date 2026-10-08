import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { FieldPath, FieldValue, SessionView, TurnResult } from '../api/types'

const STORAGE_KEY = 'intake-session-id'

// localStorage is a per-browser convenience (resume after reload); it may be unavailable.
function readStoredId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function storeId(id: string | null): void {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore: the app works without persistence.
  }
}

export interface TurnInfo {
  turn: number // increments per completed turn; used to restart highlight animations
  source: 'chat' | 'edit'
  changedPaths: FieldPath[]
  rejectedCount: number
  warnings: string[]
}

export interface SessionApi {
  session: SessionView | null
  loading: boolean
  sending: boolean
  pendingMessage: string | null
  error: ApiError | null
  failedMessage: string | null
  notice: string | null
  lastTurn: TurnInfo | null
  send: (content: string) => Promise<boolean>
  retry: () => Promise<boolean>
  editField: (path: FieldPath, value: FieldValue) => Promise<string | null>
  startOver: () => Promise<void>
  dismissError: () => void
}

export function useSession(): SessionApi {
  const [session, setSession] = useState<SessionView | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [failedMessage, setFailedMessage] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [lastTurn, setLastTurn] = useState<TurnInfo | null>(null)
  const turnCounter = useRef(0)

  const adopt = useCallback((view: SessionView) => {
    setSession(view)
    storeId(view.id)
  }, [])

  const createNew = useCallback(async () => {
    const view = await api.createSession()
    adopt(view)
    setLastTurn(null)
  }, [adopt])

  // Load once. React StrictMode runs effects twice in development; without this guard each
  // page load would create two sessions on the server.
  const loadStarted = useRef(false)
  useEffect(() => {
    if (loadStarted.current) return
    loadStarted.current = true
    async function load() {
      try {
        const storedId = readStoredId()
        if (storedId) {
          try {
            adopt(await api.getSession(storedId))
            return
          } catch (e) {
            // A restarted backend forgets in-memory sessions: start a fresh one.
            if (!(e instanceof ApiError && e.status === 404)) throw e
          }
        }
        await createNew()
      } catch (e) {
        setError(toApiError(e))
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [adopt, createNew])

  const reloadAfterConflict = useCallback(
    async (id: string) => {
      const fresh = await api.getSession(id)
      adopt(fresh)
      setNotice('This session was updated elsewhere, so it has been reloaded.')
    },
    [adopt],
  )

  const send = useCallback(
    async (content: string): Promise<boolean> => {
      if (!session || sending) return false
      setSending(true)
      setPendingMessage(content)
      setError(null)
      setNotice(null)
      setFailedMessage(null)
      try {
        const result: TurnResult = await api.sendMessage(session.id, content, session.version)
        adopt(result)
        turnCounter.current += 1
        setLastTurn({
          turn: turnCounter.current,
          source: 'chat',
          changedPaths: result.changes.map((c) => c.path),
          rejectedCount: result.rejected_updates.length,
          warnings: result.warnings,
        })
        return true
      } catch (e) {
        const err = toApiError(e)
        if (err.code === 'version_conflict') {
          await reloadAfterConflict(session.id).catch(() => undefined)
        }
        setError(err)
        setFailedMessage(content)
        return false
      } finally {
        setSending(false)
        setPendingMessage(null)
      }
    },
    [session, sending, adopt, reloadAfterConflict],
  )

  const retry = useCallback(async () => {
    return failedMessage ? send(failedMessage) : false
  }, [failedMessage, send])

  const editField = useCallback(
    async (path: FieldPath, value: FieldValue): Promise<string | null> => {
      if (!session) return 'No session'
      try {
        const view = await api.editField(session.id, path, value, session.version)
        adopt(view)
        turnCounter.current += 1
        setLastTurn({
          turn: turnCounter.current,
          source: 'edit',
          changedPaths: [path],
          rejectedCount: 0,
          warnings: [],
        })
        setNotice(null)
        return null
      } catch (e) {
        const err = toApiError(e)
        if (err.code === 'version_conflict') {
          await reloadAfterConflict(session.id).catch(() => undefined)
        }
        return err.message
      }
    },
    [session, adopt, reloadAfterConflict],
  )

  const startOver = useCallback(async () => {
    setError(null)
    setNotice(null)
    setFailedMessage(null)
    try {
      await createNew()
    } catch (e) {
      setError(toApiError(e))
    }
  }, [createNew])

  const dismissError = useCallback(() => setError(null), [])

  return {
    session,
    loading,
    sending,
    pendingMessage,
    error,
    failedMessage,
    notice,
    lastTurn,
    send,
    retry,
    editField,
    startOver,
    dismissError,
  }
}

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e
  return new ApiError(0, 'client_error', e instanceof Error ? e.message : String(e), false)
}

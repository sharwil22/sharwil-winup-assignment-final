import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { ApiError } from '../api/client'
import type { Message } from '../api/types'
import type { TurnInfo } from '../hooks/useSession'
import { AlertIcon, ArrowUpIcon, InfoIcon } from './icons'

interface Props {
  messages: Message[]
  pendingMessage: string | null
  sending: boolean
  error: ApiError | null
  failedMessage: string | null
  lastTurn: TurnInfo | null
  nextQuestion: string | null // null when the interview is complete
  onSend: (content: string) => Promise<boolean>
  onRetry: () => Promise<boolean>
  onDismissError: () => void
}

const MAX_LENGTH = 2000

function turnNote(turn: TurnInfo | null): string | null {
  if (!turn) return null
  if (turn.warnings.includes('malformed_output_fallback') || turn.warnings.includes('model_refused')) {
    return 'The assistant could not process that answer. Nothing was changed.'
  }
  if (turn.rejectedCount > 0) {
    const n = turn.rejectedCount
    return `${n} suggested ${n === 1 ? 'value was' : 'values were'} not recorded because ${n === 1 ? 'it' : 'they'} could not be confirmed from your words.`
  }
  return null
}

export function Chat(props: Props) {
  const { messages, pendingMessage, sending, error, failedMessage, lastTurn } = props
  const [draft, setDraft] = useState('')
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Scroll the log itself; scrollIntoView would also scroll the page.
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages.length, pendingMessage, error, sending, props.nextQuestion])

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    const content = draft.trim()
    if (!content || sending) return
    setDraft('')
    const ok = await props.onSend(content)
    if (!ok) setDraft(content) // keep what the user typed so nothing is lost
    inputRef.current?.focus()
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void submit()
    }
  }

  const note = turnNote(lastTurn)
  // After a direct edit in the panel the assistant's last question can be out of date
  // (e.g. answering "yes, I have children" reopens the names), so show the server's next
  // question. Only after edits: after a chat turn the model has already asked, in its own words.
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const staleQuestion =
    lastTurn?.source === 'edit' &&
    props.nextQuestion !== null &&
    !sending &&
    !lastAssistant?.content.includes(props.nextQuestion)

  // iMessage-style runs: consecutive messages from one sender sit close together, and only
  // the last bubble of a run gets a tail.
  const shown = pendingMessage
    ? [...messages, { role: 'user' as const, content: pendingMessage }]
    : messages
  const lastUserIndex = shown.map((m) => m.role).lastIndexOf('user')

  return (
    <section className="chat card" aria-label="Interview">
      <div className="chat-header">
        <span className="avatar" aria-hidden="true">
          IA
        </span>
        <h2>Intake Assistant</h2>
        <p className="chat-status">{sending ? 'typing…' : 'Fictional draft · not legal advice'}</p>
      </div>

      <div className="chat-log" role="log" aria-live="polite" ref={logRef}>
        <p className="chat-timestamp">Today</p>
        {shown.map((m, i) => {
          const next = shown[i + 1]
          const endsRun = !next || next.role !== m.role || (sending && i === shown.length - 1)
          const isPending = pendingMessage !== null && i === shown.length - 1
          return (
            <div key={i} className={`msg msg-${m.role}${endsRun ? ' run-end' : ''}`}>
              <div
                className={`bubble bubble-${m.role}${endsRun ? ' tail' : ''}${
                  isPending ? ' bubble-pending' : ''
                }`}
              >
                {m.content}
              </div>
              {m.role === 'user' && i === lastUserIndex && (
                <span className="delivery">{isPending ? 'Sending…' : 'Delivered'}</span>
              )}
            </div>
          )
        })}
        {sending && (
          <div className="msg msg-assistant run-end">
            <div className="bubble bubble-assistant tail typing" aria-label="Assistant is thinking">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        {note && !sending && (
          <p className="chat-note">
            <InfoIcon size={13} /> {note}
          </p>
        )}
        {staleQuestion && (
          <p className="chat-note chat-next">
            <strong>Next:</strong> {props.nextQuestion}
          </p>
        )}
        {error && (
          <div className="chat-error" role="alert">
            <span className="chat-error-text">
              <AlertIcon size={16} /> {error.message}
            </span>
            <div className="chat-error-actions">
              {error.retryable && failedMessage && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={async () => {
                    // The failed text was restored to the input; clear it once it has been sent.
                    if (await props.onRetry()) setDraft('')
                  }}
                  disabled={sending}
                >
                  Retry
                </button>
              )}
              <button type="button" className="btn btn-ghost btn-sm" onClick={props.onDismissError}>
                Dismiss
              </button>
            </div>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={(e) => void submit(e)}>
        <label htmlFor="composer-input" className="visually-hidden">
          Your answer
        </label>
        <div className="composer-box">
          <textarea
            id="composer-input"
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message"
            rows={1}
            maxLength={MAX_LENGTH}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!draft.trim() || sending}
            aria-label={sending ? 'Sending' : 'Send'}
          >
            <ArrowUpIcon size={16} />
          </button>
        </div>
      </form>
    </section>
  )
}

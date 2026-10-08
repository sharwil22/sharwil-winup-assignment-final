import { useEffect, useState } from 'react'
import { api } from './api/client'
import type { Health } from './api/types'
import { Chat } from './components/Chat'
import { DocumentPreview } from './components/DocumentPreview'
import { AlertIcon, InfoIcon, LogoMark, RefreshIcon, ShieldIcon } from './components/icons'
import { StatePanel } from './components/StatePanel'
import { useSession } from './hooks/useSession'

function App() {
  const s = useSession()
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null)) // the session load reports connection problems
  }, [])

  const notConfigured = health !== null && !health.model_configured

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <LogoMark />
            <div>
              <h1>Document Intake Assistant</h1>
              <p className="disclaimer">
                <ShieldIcon size={13} /> Fictional Personal Wishes Document · not legal advice
              </p>
            </div>
          </div>
          <div className="header-actions">
            {health?.provider === 'mock' && (
              <span className="badge" title="LLM_PROVIDER=mock: a rule-based stand-in for the model">
                <span className="badge-dot" /> Demo model
              </span>
            )}
            {health?.provider === 'anthropic' && health.model_configured && (
              <span className="badge badge-live">
                <span className="badge-dot" /> Claude connected
              </span>
            )}
            <button
              type="button"
              className="btn btn-on-dark"
              onClick={() => {
                if (window.confirm('Start a new interview? The current answers will be cleared.')) {
                  void s.startOver()
                }
              }}
              disabled={s.loading || s.sending}
            >
              <RefreshIcon size={15} /> Start over
            </button>
          </div>
        </div>
      </header>

      <div className="page">
        {notConfigured && (
          <div className="banner banner-warning" role="alert">
            <AlertIcon size={18} />
            <span>
              The AI model is not configured. Set <code>ANTHROPIC_API_KEY</code> in{' '}
              <code>backend/.env</code>, or set <code>LLM_PROVIDER=mock</code>, then restart the
              backend.
            </span>
          </div>
        )}
        {s.notice && (
          <div className="banner banner-info" role="status">
            <InfoIcon size={18} />
            <span>{s.notice}</span>
          </div>
        )}

        {s.loading ? (
          <div className="loading" aria-busy="true">
            <span className="spinner" /> Loading…
          </div>
        ) : !s.session ? (
          <div className="banner banner-error" role="alert">
            <AlertIcon size={18} />
            <span>{s.error?.message ?? 'Could not start a session.'}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </div>
        ) : (
          <main className="layout">
            <Chat
              messages={s.session.messages}
              pendingMessage={s.pendingMessage}
              sending={s.sending}
              error={s.error}
              failedMessage={s.failedMessage}
              lastTurn={s.lastTurn}
              nextQuestion={s.session.is_complete ? null : s.session.next_question}
              onSend={s.send}
              onRetry={s.retry}
              onDismissError={s.dismissError}
            />
            <div className="side">
              <StatePanel session={s.session} lastTurn={s.lastTurn} onEdit={s.editField} />
              <DocumentPreview
                markdown={s.session.document_markdown}
                downloadUrl={api.documentUrl(s.session.id)}
                isComplete={s.session.is_complete}
              />
            </div>
          </main>
        )}
      </div>
    </div>
  )
}

export default App

import { useState } from 'react'
import type { FieldPath, FieldStatus, FieldValue, FieldView, SessionView } from '../api/types'
import { formatValue } from '../format'
import type { TurnInfo } from '../hooks/useSession'
import { FieldEditor } from './FieldEditor'
import { ListIcon, PencilIcon, QuoteIcon } from './icons'

interface Props {
  session: SessionView
  lastTurn: TurnInfo | null
  onEdit: (path: FieldPath, value: FieldValue) => Promise<string | null>
}

const STATUS_LABEL: Record<FieldStatus, string> = {
  missing: 'Missing',
  needs_clarification: 'Needs clarification',
  captured: 'Captured',
  not_applicable: 'Not applicable',
}

export function StatePanel({ session, lastTurn, onEdit }: Props) {
  const [editing, setEditing] = useState<FieldPath | null>(null)
  const { completed, total } = session.progress
  const percent = Math.round((completed / total) * 100)
  const changed = new Set(lastTurn?.changedPaths ?? [])

  return (
    <section className="card panel" aria-labelledby="state-heading">
      <div className="card-header">
        <div className="card-title">
          <span className="card-icon" aria-hidden="true">
            <ListIcon size={16} />
          </span>
          <div>
            <h2 id="state-heading">Collected information</h2>
            <p className="card-subtitle">Edit any answer at any time</p>
          </div>
        </div>
        <div className="progress-summary">
          <span className="progress-percent">{percent}%</span>
          <span className="progress-label">{completed} of {total}</span>
        </div>
      </div>

      <div className="progress-wrap">
        <div
          className="progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={completed}
          aria-label="Interview progress"
        >
          <div className="progress-fill" style={{ width: `${(completed / total) * 100}%` }} />
        </div>
      </div>

      <ul className="fields">
        {session.fields.map((field) => {
          const isChanged = changed.has(field.path)
          return (
            <li
              // Re-keying on each turn restarts the highlight animation for changed rows.
              key={isChanged ? `${field.path}-${lastTurn?.turn}` : field.path}
              className={`field status-${field.status}${isChanged ? ' changed' : ''}${
                session.focus === field.path ? ' focus' : ''
              }`}
            >
              <div className="field-main">
                <span className="field-label">{field.label}</span>
                {editing === field.path ? (
                  <FieldEditor
                    field={field}
                    onCancel={() => setEditing(null)}
                    onSave={async (value) => {
                      const problem = await onEdit(field.path, value)
                      if (!problem) setEditing(null)
                      return problem
                    }}
                  />
                ) : (
                  <span className="field-value">
                    {field.status === 'not_applicable' ? 'Not applicable' : formatValue(field.value)}
                  </span>
                )}
                {field.status === 'captured' && editing !== field.path && (
                  <Provenance field={field} />
                )}
                {field.status === 'needs_clarification' && editing !== field.path && (
                  <p className="field-note">
                    {field.note}
                    {field.candidate !== null && <> · proposed: {formatValue(field.candidate)}</>}
                  </p>
                )}
              </div>

              <div className="field-side">
                <span className={`chip chip-${field.status}`}>{STATUS_LABEL[field.status]}</span>
                {(field.status === 'not_applicable' || editing === field.path) && (
                  <span className="icon-spacer" aria-hidden="true" />
                )}
                {field.status !== 'not_applicable' && editing !== field.path && (
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => setEditing(field.path)}
                    aria-label={`Edit ${field.label}`}
                    title="Edit"
                  >
                    <PencilIcon size={15} />
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** "Your words": the exact phrase a captured value came from, so every answer is traceable. */
function Provenance({ field }: { field: FieldView }) {
  const replaced =
    field.previous_value !== null && field.previous_value !== undefined
      ? ` · was ${formatValue(field.previous_value)}`
      : ''
  if (field.source === 'edit') {
    return <p className="field-source">Edited by you{replaced}</p>
  }
  if (!field.evidence) return null
  return (
    <p className="field-source" title="The words in your message this answer was taken from">
      <QuoteIcon size={11} />
      <span className="field-source-quote">“{field.evidence}”</span>
      {field.source_turn !== null && <span> · message {field.source_turn}</span>}
      {replaced}
    </p>
  )
}

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { errorReply, installFakeBackend, withName } from './test/fakeBackend'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

async function renderReady() {
  render(<App />)
  await screen.findByText('Hello! What is your full name?')
}

function fieldRow(label: string): HTMLElement {
  const row = screen.getAllByText(label, { selector: '.field-label' })[0].closest('li')
  if (!row) throw new Error(`no row for ${label}`)
  return row
}

describe('App', () => {
  it('starts a session and shows the opening question, fields and draft', async () => {
    installFakeBackend()
    await renderReady()
    expect(screen.getByText('Demo model')).toBeInTheDocument()
    expect(screen.getByText(/not legal advice/i, { selector: '.disclaimer' })).toBeInTheDocument()
    expect(within(fieldRow('full name')).getByText('Missing')).toBeInTheDocument()
    expect(screen.getByText('0 of 9')).toBeInTheDocument()
    expect(screen.getByText('FICTIONAL DRAFT — NOT LEGAL ADVICE.')).toBeInTheDocument()
  })

  it('sends a message and updates chat, fields and document from the response', async () => {
    const backend = installFakeBackend()
    backend.queue('POST /api/sessions/s1/messages', () => ({
      status: 200,
      body: withName(backend.session, 'Jane Smith', 'My name is Jane Smith'),
    }))
    await renderReady()

    await userEvent.type(screen.getByLabelText('Your answer'), 'My name is Jane Smith{Enter}')

    expect(await screen.findByText('Thanks, I have noted that. What is your home address?')).toBeInTheDocument()
    const row = fieldRow('full name')
    expect(within(row).getByText('Jane Smith')).toBeInTheDocument()
    expect(within(row).getByText('Captured')).toBeInTheDocument()
    expect(row).toHaveClass('changed')
    // "Your words": the value is traced back to the user's message
    expect(within(row).getByText('“My name is Jane Smith”')).toBeInTheDocument()
    expect(within(row).getByText('· message 1')).toBeInTheDocument()
    expect(screen.getByText('I, Jane Smith')).toBeInTheDocument()
    expect(screen.getByLabelText('Your answer')).toHaveValue('')

    const sent = backend.calls.find((c) => c.method === 'POST' && c.path.endsWith('/messages'))
    expect(sent?.body).toEqual({ content: 'My name is Jane Smith', expected_version: 0 })
  })

  it('keeps the message and offers retry when the model is unavailable', async () => {
    const backend = installFakeBackend()
    backend.queue(
      'POST /api/sessions/s1/messages',
      () => errorReply(503, 'llm_unavailable', 'The AI model is temporarily unavailable.', true),
      () => ({ status: 200, body: withName(backend.session, 'Jane Smith', 'Jane Smith') }),
    )
    await renderReady()

    await userEvent.type(screen.getByLabelText('Your answer'), 'Jane Smith{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('temporarily unavailable')
    expect(screen.getByLabelText('Your answer')).toHaveValue('Jane Smith')

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

    expect(await screen.findByText('Thanks, I have noted that. What is your home address?')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Your answer')).toHaveValue('')
  })

  it('reloads the session and explains when the version is stale', async () => {
    const backend = installFakeBackend()
    backend.queue('POST /api/sessions/s1/messages', () =>
      errorReply(409, 'version_conflict', 'This session changed in another request.', true),
    )
    await renderReady()

    await userEvent.type(screen.getByLabelText('Your answer'), 'hello{Enter}')

    expect(await screen.findByText(/updated elsewhere/)).toBeInTheDocument()
    expect(backend.calls.filter((c) => c.path === '/api/sessions/s1' && c.method === 'GET')).toHaveLength(1)
  })

  it('edits a field directly and shows validation errors from the server', async () => {
    const backend = installFakeBackend()
    backend.queue(
      'PATCH /api/sessions/s1/fields',
      () => errorReply(422, 'validation_error', "full_name: 'full_name' must not be empty", false),
      () => ({
        status: 200,
        body: {
          ...backend.session,
          version: 1,
          fields: backend.session.fields.map((f) =>
            f.path === 'full_name'
              ? { ...f, value: 'Jane A. Smith', status: 'captured', source: 'edit' }
              : f,
          ),
        },
      }),
    )
    await renderReady()

    await userEvent.click(screen.getByRole('button', { name: 'Edit full name' }))
    const input = screen.getByLabelText('full name')
    await userEvent.type(input, ' {Enter}')
    expect(await screen.findByText("full_name: 'full_name' must not be empty")).toBeInTheDocument()

    await userEvent.clear(input)
    await userEvent.type(input, 'Jane A. Smith{Enter}')

    expect(await within(fieldRow('full name')).findByText('Jane A. Smith')).toBeInTheDocument()
    expect(within(fieldRow('full name')).getByText('Edited by you')).toBeInTheDocument()
    const patch = backend.calls.filter((c) => c.method === 'PATCH').at(-1)
    expect(patch?.body).toEqual({ path: 'full_name', value: 'Jane A. Smith', expected_version: 0 })
  })

  it('shows the next question after an edit reopens a field', async () => {
    const backend = installFakeBackend()
    backend.queue('PATCH /api/sessions/s1/fields', () => ({
      status: 200,
      body: {
        ...backend.session,
        version: 1,
        focus: 'children_names',
        next_question: "What are your children's names?",
      },
    }))
    await renderReady()
    expect(screen.queryByText(/^Next:/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Edit whether you have children' }))
    await userEvent.selectOptions(screen.getByLabelText('whether you have children'), 'yes')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText("What are your children's names?")).toBeInTheDocument()
  })

  it('does not repeat the question after a chat turn, even in different words', async () => {
    const backend = installFakeBackend()
    const result = withName(backend.session, 'Jane Smith', 'Jane Smith')
    backend.queue('POST /api/sessions/s1/messages', () => ({
      status: 200,
      body: {
        ...result,
        next_question: 'What is your home address?',
        messages: [
          ...backend.session.messages,
          { role: 'user', content: 'Jane Smith' },
          { role: 'assistant', content: 'Lovely to meet you, Jane. Where do you live?' },
        ],
      },
    }))
    await renderReady()
    await userEvent.type(screen.getByLabelText('Your answer'), 'Jane Smith{Enter}')
    expect(await screen.findByText('Lovely to meet you, Jane. Where do you live?')).toBeInTheDocument()
    expect(screen.queryByText(/^Next:/)).not.toBeInTheDocument()
  })

  it('warns when the real model is selected but not configured', async () => {
    installFakeBackend({ provider: 'anthropic', configured: false })
    await renderReady()
    await waitFor(() => expect(screen.getByText(/The AI model is not configured/)).toBeInTheDocument())
    expect(screen.queryByText('Demo model')).not.toBeInTheDocument()
  })

  it('resumes a stored session after a page reload', async () => {
    localStorage.setItem('intake-session-id', 's1')
    const backend = installFakeBackend()
    await renderReady()
    expect(backend.calls.some((c) => c.method === 'POST' && c.path === '/api/sessions')).toBe(false)
  })

  it('starts a new session if the stored one no longer exists', async () => {
    localStorage.setItem('intake-session-id', 'gone')
    const backend = installFakeBackend()
    await renderReady()
    expect(backend.calls.some((c) => c.method === 'POST' && c.path === '/api/sessions')).toBe(true)
    expect(localStorage.getItem('intake-session-id')).toBe('s1')
  })

  it('shows a clear message when the backend is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    render(<App />)
    expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument()
  })
})

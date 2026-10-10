# TRD — Document Intake Assistant

_Wenup engineering technical test · as of 2026-10-07_

Related documents: [PRD](PRD.md) · [Implementation Plan](IMPLEMENTATION_PLAN.md) · [Step by Step](STEP_BY_STEP.md)

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2 | Schema-first models double as validation and the OpenAPI contract |
| LLM | Anthropic API, `claude-opus-5-5`, structured outputs (JSON schema) | Valid JSON by construction; still validated by our Pydantic contract |
| LLM fallback | Deterministic `MockProvider` with fixtures | Runs with no API key; drives tests |
| Document | Jinja2 Markdown template, rendered by code | No LLM in the document path, so it cannot invent content |
| Frontend | React + TypeScript + Vite, `react-markdown` | Small, fast setup; typed API client |
| Storage | In-memory session store behind a `SessionRepository` interface | Enough for the exercise; swappable for Redis or Postgres |
| Tests | pytest + FastAPI `TestClient`; Vitest + Testing Library against a fake backend | Fast, no network |
| Tooling | `uv`, ruff, mypy, `make`, `.env` + `.env.example` | One-command setup, secrets out of git |

## Architecture

Four layers with one-way dependencies: **UI → API → application logic → (LLM adapter, document generator)**. The domain layer has no knowledge of HTTP or of any LLM vendor. The model only proposes; validated code writes the state.

```
┌──────────────────────── Browser UI · React + TypeScript ────────────────────────┐
│   [ Chat ]            [ State panel + status chips ]        [ Document preview ] │
└───────────────────────────────────────┬─────────────────────────────────────────┘
                                        │ JSON over HTTP, versioned state
┌───────────────────────────────────────▼─────────────────────────────────────────┐
│               FastAPI · routes, DTOs, error envelope, version check             │
└───────────────────────────────────────┬─────────────────────────────────────────┘
┌───────────────────────────────────────▼─────────────────────────────────────────┐
│ Interview service · one user turn, steps run left to right                      │
│                                                                                 │
│  [Planner] ──▶ [LLM provider] ──▶ [VALIDATOR] ──▶ [Reducer] ──▶ [Doc generator] │
│  picks next     Anthropic or       schema +        pure state     Jinja2,       │
│  field, never   Mock; proposes     evidence;       update; flags  no LLM        │
│  re-asks        updates            drops bad ones  conflicts      involved      │
└──────────────────────────────────────────────────────┬──────────────────────────┘
                                                       │ saves new version
┌──────────────────────────────────────────────────────▼──────────────────────────┐
│        Session store · WishesState (source of truth), messages, change log      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

The validator is the gate: nothing the model returns reaches the state, the preview or the document without passing it.

### Repository layout

```
backend/app/
  api/          routes.py, schemas.py (request/response DTOs), errors.py
  domain/       models.py (WishesState, FieldStatus), updates.py (ProposedUpdate), values.py,
                reducer.py, validation.py, planner.py
  llm/          interface.py (LLMProvider), contracts.py, prompts.py, anthropic_provider.py,
                mock_provider.py (ScriptedProvider, RuleBasedProvider), factory.py
  documents/    generator.py, templates/wishes.md.j2
  services/     interview.py (one turn), sessions.py (SessionService use cases),
                session_store.py (Session, InMemorySessionRepository)
  config.py     settings from env, provider selection
backend/tests/  fixtures/llm_responses/*.json, test_*.py
frontend/src/   api/client.ts, components/{Chat,StatePanel,DocumentPreview}.tsx
```

## Data model

Each field is wrapped in a `Field[T]` so status and provenance travel with the value:

```python
class FieldStatus(str, Enum):
    MISSING = "missing"
    NEEDS_CLARIFICATION = "needs_clarification"
    CAPTURED = "captured"
    NOT_APPLICABLE = "not_applicable"

class Field[T](BaseModel):           # frozen; updates return copies
    value: T | None = None           # only ever a value the user confirmed
    status: FieldStatus = FieldStatus.MISSING
    candidate: T | None = None       # unclear or conflicting proposal awaiting clarification
    note: str | None = None          # why clarification is needed
    source_turn: int | None = None   # which user message set it
    source: "chat" | "edit" | None   # provenance, shown in the UI ("Your words")
    evidence: str | None             # the user's own words that support `value`
    previous_value: T | None         # what a correction replaced

class Executor(BaseModel):
    name: Field[str]
    relationship: Field[str]

class Gift(BaseModel):
    item: str
    recipient: str

class WishesState(BaseModel):
    full_name: Field[str]
    home_address: Field[str]
    covers_worldwide_assets: Field[bool]
    has_children: Field[bool]
    children_names: Field[list[str]]
    executor: Executor
    specific_gifts: Field[list[Gift]]   # [] + CAPTURED means "none"
    additional_wishes: Field[str]       # "" + CAPTURED means "none"
    version: int = 0
```

Proposed changes are `ProposedUpdate` objects in `domain/updates.py` (path, value, kind, certainty, evidence, source = `chat` | `ui_edit`). The LLM contract reuses this type, so the domain never imports from `llm/`.

A `Session` is an immutable snapshot: `id`, `state`, `messages` (role, content, turn), `change_log` (every applied change), `turn` (user messages handled) and `version`. The session `version` goes up on every save, including turns that change no field (the messages still change), and is what clients send back as `expected_version`. The flat view in the brief (`"full_name": "Jane Smith"`) is exposed as `state.as_plain()` for the UI and the document.

## LLM contract

One model call per user turn, using **structured outputs** (`output_config.format` with a JSON schema generated from `TurnExtraction`). Forced tool use is not used: current Claude models reject `tool_choice` `any`/`tool`. The response is still parsed through the same Pydantic model, because a truncated or refused response may not match. The contract lives in `llm/contracts.py`, separate from the domain's `ProposedUpdate` (`FieldUpdate.to_proposed()` converts).

```python
class FieldUpdate(BaseModel):          # extra="forbid" -> additionalProperties: false
    path: FieldPath                    # one of the 9 paths
    value: bool | str | list[str] | list[GiftOut]
    kind: Literal["new", "correction"]
    certainty: Literal["explicit", "unclear"]
    evidence: str                      # exact user words supporting the value

class TurnExtraction(BaseModel):
    updates: list[FieldUpdate]
    reply: str                         # assistant message to show the user
    asks_about: FieldPath | None       # the field the reply's question targets
```

Each turn is a fresh single-message request: a static, versioned system prompt (`PROMPT_VERSION`) plus one user message holding the CAPTURED fields, the REMAINING fields in interview order, the last 10 messages, and the latest user message fenced in `<user_message>` tags (treated as data, not instructions). Rules in the prompt:

- Extract only what the user stated in the latest message; never guess; quote evidence.
- Several fields per message, in any order.
- Mark vague answers `unclear`; mark explicit changes `correction`.
- Ask about the first remaining field not answered, or the unclear one; never ask about a captured field; report it in `asks_about`.
- If the latest message contradicts a captured value, propose the implied value for that field anyway (it becomes a conflict the planner asks about); never resolve it silently.

Request settings: model `claude-opus-5-5` (configurable via `LLM_MODEL`), `effort: low` (`LLM_EFFORT`) for fast turns, `max_tokens` 8000, timeout 30 s with one SDK retry, and `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) so a safety-declined request is re-run server-side on a recommended fallback model.

## Turn pipeline

1. **Receive** the user message and load the session.
2. **Plan**: `planner.next_focus(state)` returns the first field that is needs-clarification, then missing, in a fixed interview order.
3. **Call the model** through `LLMProvider.extract(context) -> TurnExtraction`, with a 30 s timeout. A refusal keeps the state unchanged and asks the planner's question; timeouts, rate limits and network errors raise `LLMUnavailable` (HTTP 503, state unchanged).
4. **Validate the shape**: Pydantic parse. On failure, retry once with the validation error appended; if that fails too, keep state unchanged and reply with a deterministic fallback question for `next_focus`.
5. **Validate the semantics** per update (`domain/validation.py`): type matches the path; non-empty strings; `evidence` must appear in the user message (guards against invented facts); `children_names` rejected while `has_children` is false.
6. **Reduce**: `reducer.apply(state, updates) -> (new_state, changes, conflicts)` is a pure function.
    - `unclear` sets NEEDS_CLARIFICATION with the proposal in `candidate`, never CAPTURED.
    - A `new` value that differs from a CAPTURED value is a **conflict**: the old value stays, the proposal goes to `candidate`, the field becomes NEEDS_CLARIFICATION, and the reply asks which is right. The next explicit answer resolves it.
    - A `correction` overwrites and is logged in `change_log`.
    - `has_children = false` sets `children_names` to NOT_APPLICABLE; flipping it back to true sets it to MISSING.
    - Children's names given while `has_children` is unanswered imply "yes"; names given while a `has_children` conflict is open wait in `candidate` until it is resolved.
    - Two updates for the same field in one turn: the second is rejected by validation.
7. **Choose the reply**: the planner decides *what* to ask, the model only *how*. The model's reply is used only when its `asks_about` equals the planner's next focus and the turn had no conflicts and no rejected updates; otherwise it is replaced by the planner's templated question (with "Thanks, I've noted that." when something changed). The reply is never trusted to report state; the UI shows state from the server.
8. **Persist**: append the user and assistant messages, extend the change log, and save with optimistic concurrency (`save(session, expected_version)` fails if anyone saved in between). On a model error nothing is saved, not even the user's message, so a retry is clean.
9. **Respond** with state, document, changes, rejected updates and the reply.

## API contract

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/api/sessions` | — | `SessionView` with the opening question |
| GET | `/api/sessions/{id}` | — | `SessionView` |
| POST | `/api/sessions/{id}/messages` | `{content: str, expected_version: int}` | `TurnResult` |
| PATCH | `/api/sessions/{id}/fields` | `{path, value, expected_version}` | `SessionView` (direct UI edit, same validation and reducer) |
| GET | `/api/sessions/{id}/document` | — | `text/markdown` |
| GET | `/api/health` | — | `{status, provider, model_configured}` |

`SessionView` = `{id, version, fields[] (path, label, value, status, candidate, note, source, source_turn, evidence, previous_value), state (flat confirmed values), messages, document_markdown, progress: {completed, total}, is_complete, focus, next_question}`.
`TurnResult` = `SessionView` + `{reply, changes[], rejected_updates[], warnings[]}`.
A stale `expected_version` returns 409, checked before the model is called (no wasted call) and again atomically on save. The preview can never show an outdated state. Request bodies forbid unknown fields; messages are 1 to 2,000 characters. The model call runs in a worker thread (sync route), so it never blocks the event loop.

Errors use one shape: `{error: {code, message, retryable}}`.

| Code | HTTP | Cause |
| --- | --- | --- |
| `session_not_found` | 404 | Unknown id |
| `internal_error` | 500 | Unexpected bug; details logged, never returned |
| `version_conflict` | 409 | Stale client state |
| `validation_error` | 422 | Bad request body or direct-edit value |
| `llm_unavailable` | 503 | Timeout, network or provider error after retry; state unchanged |
| `llm_not_configured` | 503 | `LLM_PROVIDER=anthropic` with no `ANTHROPIC_API_KEY` |

Malformed model output is **not** an HTTP error: it is handled in the pipeline (step 4) and reported in `warnings`.

## Document generation

`documents/generator.py` renders `wishes.md.j2` from `state.as_plain()`. It is pure and deterministic, so it is snapshot-tested.

- A banner at the top and a footer: **"FICTIONAL DRAFT — NOT LEGAL ADVICE. Generated for a technical exercise."**
- Sections: Declarant, Scope of assets, Children, Executor, Specific gifts, Additional wishes.
- Missing values render as `[To be confirmed: home address]`; needs-clarification values render with a marker. Nothing is filled with defaults.
- The document carries a "Draft status: incomplete (6 of 9 sections)" line until every required field is captured.

## Configuration and secrets

- `LLM_PROVIDER=mock|anthropic` (default `mock`), `ANTHROPIC_API_KEY`, `LLM_MODEL` (default `claude-opus-5-5`), `LLM_EFFORT=low`, `LLM_TIMEOUT_S=30`.
- `.env` is gitignored; `.env.example` is committed. Settings load with `pydantic-settings` at startup.
- With `anthropic` and no key, the server still starts; `/api/health` and chat calls report `llm_not_configured`, and the UI shows a banner telling the user how to fix it.

## Frontend

React + TypeScript (Vite), no UI library. Two columns on desktop (chat left; collected information and the draft document right, each scrolling internally); a single stacked column under 900 px.

- `api/types.ts` mirrors the backend DTOs; `api/client.ts` turns every failure (including network errors) into an `ApiError` carrying the backend's `code` and `retryable`.
- `hooks/useSession.ts` owns all server interaction: load or resume (session id in `localStorage`, wrapped in try/catch; a 404 after a backend restart starts a fresh session), send, retry, direct edit, start over. It loads exactly once (React StrictMode runs effects twice in development).
- `Chat`: optimistic user bubble and typing indicator; Enter sends, Shift+Enter adds a line; on failure the text goes back into the input and retryable errors offer **Retry**; quiet notes for rejected values or an unprocessable answer; a **Next:** hint when the server's next question differs from the assistant's last one (e.g. after a panel edit reopens a field).
- `StatePanel`: progress bar, one row per field with a status chip, the current focus marked, rows changed by the last turn highlighted, clarification notes with the proposed value, and inline **Edit** (`FieldEditor`: yes/no select, comma-separated names, one "item to person" gift per line).
- `DocumentPreview`: the server-rendered Markdown via `react-markdown` (no raw HTML) and a **Download .md** link.
- Banners: model not configured, session reloaded after a version conflict, backend unreachable. A "Demo model" badge when the mock provider is active.
- The client stores only the session id; every view comes from the server response, so the preview always matches the confirmed state.

## Testing strategy

| Area | What the tests prove |
| --- | --- |
| Reducer | Multi-field update; correction overwrites and logs; conflict keeps old value and flags it; unclear never becomes captured; has_children toggling; "none" for optional fields |
| Validation | Wrong type rejected; evidence not in message rejected; unknown path rejected; children names while has_children false rejected |
| LLM fixtures | 12 recorded responses: valid, multi-field, executor + relationship, ambiguous, correction, contradiction, invented fact, reply asking a captured field, wrong types, malformed then valid, malformed twice, empty |
| Error handling | Timeout and provider error return 503 with state unchanged; malformed twice gives a fallback reply; missing key gives `llm_not_configured` |
| Planner | Next question skips captured and not-applicable fields; never re-asks a captured field |
| Document | Snapshot of a complete state; placeholders for gaps; disclaimer always present |
| API | Full conversation through `TestClient`; turn result shape; rejected updates reported; 409 stale and concurrent saves (no model call); 404; 422 bodies and edits; 503 with session unchanged; malformed output is 200 + warnings; 500 hides internals; direct edits; Markdown download; OpenAPI lists every endpoint |
| Live eval (optional) | `make eval` runs 6 scripted conversations against the real model and prints a pass/fail table; not in CI |

## Replacing the mock with a real provider

`LLMProvider` is a protocol with one method, `extract(context: TurnContext) -> TurnExtraction`. The Anthropic adapter builds the prompt and parses the structured output; `ScriptedProvider` replays fixtures for tests and `RuleBasedProvider` (regex rules) is the no-key demo default. Both go through the same `parse_extraction`. Adding OpenAI or a local model means one new adapter class and one config value; nothing above the `llm/` package changes.

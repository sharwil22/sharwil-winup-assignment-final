# sharwil-winup-assignment

# Document Intake Assistant

A small web app that interviews a user in chat, keeps a **validated structured record** of their answers, and renders a draft **fictional** Personal Wishes Document from that record. Built for the Wenup engineering technical test.

> Fictional document. Not legal advice.

**▶ 3-minute video walkthrough:** [docs/VIDEO_WALKTHROUGH.md](docs/VIDEO_WALKTHROUGH.md): what it is, the approach, how it was built, and the technical terms.

![Interview in progress: chat on the left, collected information and draft on the right](docs/screenshots/desktop.png)

**Answer provenance:** every captured answer shows the exact words it came from (*"my brother James" · message 5*), and corrections show what they replaced, so nothing in the record is unexplained.

**The core rule: the LLM proposes, the application decides.** The model only suggests field updates in a fixed schema. Deterministic code validates them, applies them to the state, chooses the next question, and renders the document from a template. The model is used for understanding messy language; it is kept away from the facts and the document.

---

## Quick start (no API key needed)

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, `make`.

```bash
make install   # backend + frontend dependencies; creates backend/.env from .env.example
make dev       # backend http://localhost:8000, frontend http://localhost:5173 (Ctrl+C stops both)
```

Open **http://localhost:5173**. Screenshots: [interview](docs/screenshots/desktop.png), [clarification, dark mode](docs/screenshots/clarification-dark.png), [draft document](docs/screenshots/document.png), [answer provenance](docs/screenshots/provenance.png).

 Chat on the left; on the right, the collected information (status per field, inline **Edit**) and the live draft (**Download .md**).

With no key the app uses a **rule-based demo model** (a "Demo model" badge shows in the header). It handles the happy path and a few phrasings ("My name is…", "my brother James", "no kids", "actually…"), but it is a stand-in, not language understanding.

Try: `I'm Jane Smith, no kids, 4 High Street, Leeds LS1 1AA` → `Yes` → `My brother James` → `Actually, change my executor to my sister Anna` → `I'd like to leave my watch to Anna` → `None`.

## Using Claude

Edit `backend/.env` and restart:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
LLM_MODEL=claude-opus-5-5   # optional; any current Claude model
LLM_EFFORT=low              # optional; low | medium | high
```

`.env` is gitignored; only `.env.example` is committed. If `anthropic` is selected without a key, the app still starts: the UI shows a banner and chat requests return a clear `llm_not_configured` error.

`make eval` runs eight scripted conversations (`--repeat N` runs each N times, since model output varies) against the configured model and prints a pass/fail table (a few cents per run). With `claude-opus-5-5` at low effort all eight pass, at about 3–5 s per turn.

## Commands

| Command | What it does |
| --- | --- |
| `make install` | Install dependencies, create `backend/.env` |
| `make dev` | Run backend and frontend together |
| `make test` | Backend (pytest, 155 tests) and frontend (Vitest, 15 tests); no network, no key |
| `make lint` | ruff, ruff format, mypy (strict), oxlint, tsc |
| `make eval` | Scripted conversations against the real model |

API docs (OpenAPI) are at http://localhost:8000/docs while the backend runs.

## Deploying to Render

The repository includes a `render.yaml` Blueprint and `Dockerfile` for a single-service deployment. The container builds the frontend and serves it from FastAPI, keeping browser and API requests on the same origin.

1. Push this repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com), choose **New > Blueprint** and select the repository.
3. Enter your Anthropic key when Render prompts for `ANTHROPIC_API_KEY`. Keep it in Render's environment settings; never add it to GitHub.
4. Create the Blueprint and wait for the service to finish deploying. Open its `onrender.com` URL.

The Blueprint uses Render's free web-service plan. Free instances can sleep when idle, and interview sessions are in memory, so they reset on restart or redeploy. For persistent sessions, add a database-backed repository before using the app for real users. This app creates fictional drafts only; it is not legal advice.

---

## How it works

```
Browser (React)  ──JSON, versioned──▶  FastAPI routes ──▶ SessionService
                                                              │
               ┌──────────── one user turn (services/interview.py) ────────────┐
               │ Planner ─▶ LLM provider ─▶ Validator ─▶ Reducer ─▶ Document   │
               │ next field  Claude / mock   types,       pure state  Jinja2    │
               │ to ask      proposes        evidence,    update      template, │
               │             updates         consistency              no LLM    │
               └───────────────────────────────────────────────────────────────┘
                                                              │
                                    Session store (WishesState = source of truth)
```

1. **State.** Nine fields, each with a status: `missing`, `needs_clarification`, `captured`, `not_applicable`. A field's `value` only ever holds a confirmed answer; unclear or conflicting answers wait in a separate `candidate` slot.
2. **Model call.** One request per turn using **structured outputs** (a JSON schema generated from the Pydantic contract). The model returns proposed `updates` (each with `kind` new/correction, `certainty` explicit/unclear and the user's own words as `evidence`), a `reply`, and `asks_about` (the field its question targets).
3. **Validation.** Types per field; **evidence must appear in the user's message** (the main guard against invented facts); consistency (no children's names after "no children").
4. **Reducer** (pure function). Unclear answers are never captured. A new answer that disagrees with a captured one is a **conflict**: the old value stays and the user is asked which is right. An explicit **correction** overwrites. "No children" makes the names field not applicable.
5. **Reply.** The server's planner decides *what* to ask (it never re-asks a captured field); the model only decides *how*. Its wording is used only if `asks_about` matches the planner and nothing was rejected or conflicting.
6. **Document.** Rendered by a template from confirmed values only, with visible placeholders for gaps and the fictional/not-legal-advice label at the top and bottom.

### Failure handling

| Situation | What happens |
| --- | --- |
| Malformed model output | Retry once with the parse error as a hint; if it fails again, nothing changes and the planner's question is asked (HTTP 200 with `warnings`) |
| Model refuses | Server-side fallback model (`fallbacks: "default"`); if still refused, nothing changes and the question is repeated |
| Timeout, rate limit, network, 5xx | HTTP 503 `llm_unavailable` (retryable); **nothing is saved**, so Retry is clean |
| Missing or invalid key | HTTP 503 `llm_not_configured` with the fix; health endpoint and UI banner report it |
| Two tabs or a double submit | Optimistic concurrency: a stale `expected_version` gets 409 before the model is called; the UI reloads |
| Anything unexpected | HTTP 500 with a generic message; details only in the server log |

### Key decisions and trade-offs

| Decision | Trade-off |
| --- | --- |
| Model proposes, code decides | More code than "let the model fill a form", but every fact is validated and every rule is testable |
| Evidence must quote the user | Occasionally rejects a correct value the model paraphrased; the user is simply asked again |
| Server picks the next question | Conversation is a little more scripted; "never re-ask a captured field" is guaranteed rather than hoped for |
| Template document, no LLM | Less natural prose; the draft can never contain anything that isn't in the confirmed state |
| Structured outputs, not forced tool use | Current Claude models reject forced `tool_choice`; structured outputs constrain the JSON. Output is still validated, since truncation or refusal can break it |
| In-memory sessions | Lost on restart (the UI starts a fresh one); storage is behind an interface for a real database |
| Deterministic regex mock as default | Runs without a key; clearly not language understanding |

## Swapping the model provider

The application talks to one interface:

```python
class LLMProvider(Protocol):
    def extract(self, ctx: TurnContext) -> TurnExtraction: ...
```

`AnthropicProvider` builds the prompt, calls the API with the JSON schema, and maps SDK errors onto the app's own (`LLMUnavailable`, `LLMNotConfigured`, `LLMMalformedOutput`, `LLMRefused`). To use another provider, write one class with `extract()` and add a branch in `backend/app/llm/factory.py`. The contract, prompt, validation, reducer, API and UI don't change. The two offline providers (`ScriptedProvider` for tests, `RuleBasedProvider` for the demo) already prove the seam.

## Testing

- **Domain** (state, validation, reducer, planner): pure-function tests, including "never asks the same field twice" over a full interview.
- **Document**: snapshot files (`backend/tests/snapshots/*.md`) plus checks that unclear or conflicting values never appear and that user text can't inject Markdown.
- **Model handling**: 12 recorded model responses in `backend/tests/fixtures/llm_responses/` (valid, multi-field, ambiguous, correction, contradiction, invented fact, reply asking a captured field, wrong types, malformed then valid, malformed twice, empty), each run through the real pipeline. The Claude adapter is tested against a fake SDK client (request shape, refusal, truncation, every error class).
- **API**: full conversation, every error code, stale versions, model failures leave the session unchanged.
- **UI**: component tests against a fake backend (send, retry, 409 reload, edit errors, resume). The app was also driven in headless Chrome, which found six issues unit tests missed (see the build journal).
- **Live eval** (`make eval`): six scripted conversations against the real model, checking the final state.

## Project layout

```
backend/app/
  domain/      models.py, updates.py, validation.py, reducer.py, planner.py   (no HTTP, no LLM)
  documents/   generator.py, templates/wishes.md.j2
  llm/         contracts.py, interface.py, prompts.py, anthropic_provider.py, mock_provider.py, factory.py
  services/    interview.py (one turn), sessions.py (use cases), session_store.py
  api/         routes.py, schemas.py, errors.py
backend/tests/ unit, fixture, API and snapshot tests
backend/scripts/eval.py   live evaluation
frontend/src/  api/, hooks/useSession.ts, components/, format.ts
docs/          PRD, TRD, plan, step-by-step guide, build journal, screenshots
```

## Known limitations

- Sessions are in memory: a backend restart forgets them.
- No authentication; anyone with a session id can read that session.
- The demo provider is regex-based. For example, it takes "Just call me Jane" as the full name, which `make eval` flags.
- One interview language (English) and one fictional jurisdiction.
- No streaming of model replies; each turn waits for the full, validated response.

What I would do for production is in [PRODUCTION_NOTES.md](PRODUCTION_NOTES.md).

## Documents

| Document | Contents |
| --- | --- |
| [docs/VIDEO_WALKTHROUGH.md](docs/VIDEO_WALKTHROUGH.md) | Narrated 3:20 video, chapters, glossary of technical terms, transcript |
| [docs/VOICEOVER_SCRIPT.md](docs/VOICEOVER_SCRIPT.md) | The video's narration, timed, with what is on screen for each line |
| [docs/BRIEF_COMPLIANCE.md](docs/BRIEF_COMPLIANCE.md) | Every requirement in the brief, how it is met, and the evidence |
| [AI_LOG.md](AI_LOG.md) | How AI tools were used: key prompts, iterations, output questioned or corrected |
| [PRODUCTION_NOTES.md](PRODUCTION_NOTES.md) | What I would change for production |
| [docs/BUILD_JOURNAL.md](docs/BUILD_JOURNAL.md) | What was built in each phase, how and why, including what changed along the way |
| [docs/PRD.md](docs/PRD.md) · [docs/TRD.md](docs/TRD.md) | Product and technical requirements |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) · [docs/STEP_BY_STEP.md](docs/STEP_BY_STEP.md) | Plan and build guide |

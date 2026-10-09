# Project Documentation

## 1. Project Overview

The Document Intake Assistant is a conversational application that collects user-provided information, validates it into structured state, and generates a draft Personal Wishes Document from confirmed answers.

The project demonstrates how an AI-assisted application can handle multi-turn conversations while maintaining explicit state, validating proposed updates, and generating predictable output.

The application is designed as a technical demonstration. The generated document is fictional, is not legal advice, and has no legal effect.

### Core Design Principle

**The model proposes; the application decides.**

The language model proposes structured field updates. The application validates those proposals, applies accepted changes through deterministic state-management logic, determines the next question, and renders the draft from confirmed information.

The model does not directly control the application's state or write the final document.

## 2. Key Features

### Conversational Information Collection

The application collects information through a multi-turn chat interface. Users can provide answers in natural language and progressively complete the required fields.

### Structured Data Extraction

User responses are converted into structured extraction proposals. The backend uses typed models to represent and validate incoming data.

### Field Status Tracking

Each field has an explicit status:

- `missing` — information has not been provided.
- `needs_clarification` — the answer is ambiguous or requires clarification.
- `captured` — a value has been accepted.
- `not_applicable` — the field does not apply.

This makes the current state of the conversation easier to inspect and manage.

### Validation and Corrections

The application validates proposed updates before accepting them. Ambiguous or contradictory responses can require clarification rather than silently replacing a previously confirmed value.

Users can also correct captured information through the chat or the field-editing interface.

### Question Planning

A deterministic planner selects the next field to ask about. Fields requiring clarification are prioritized before missing fields, while completed and not-applicable fields are skipped.

### Draft Generation

The backend generates a Markdown draft using a template and the confirmed application state. The user can preview and download the generated draft.

### Error Handling and Version Control

The API uses structured error responses. Optimistic concurrency checks help prevent updates based on stale session versions.

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI |
| Data validation | Pydantic |
| Language model integration | Anthropic SDK and provider abstraction |
| Template generation | Jinja2, Markdown |
| Backend testing | pytest, FastAPI TestClient |
| Frontend testing | Vitest, Testing Library |
| Deployment | Render |

## 4. Application Workflow

The application follows this sequence:

1. The user creates or resumes a conversation session.
2. The user submits a message containing information or a correction.
3. The backend requests structured extraction from the configured provider.
4. The proposed updates are validated.
5. The reducer applies accepted updates to the session state.
6. The planner selects the next question.
7. The application generates a draft from the confirmed state.
8. The frontend displays the updated fields, progress, and draft.

```text
User Message
     |
     v
Structured Extraction
     |
     v
Validation
     |
     v
State Reducer
     |
     v
Question Planner
     |
     v
Draft Generator
     |
     v
Updated Response to User
```

## 5. Information Collected

The application tracks nine fields:

1. Full name
2. Home address
3. Whether worldwide assets are covered
4. Whether the user has children
5. Children's names
6. Executor's name
7. Executor's relationship
8. Specific gifts
9. Additional wishes

The exact information requested depends on the current field status and the conversation.

## 6. Provider Architecture

The application uses a provider abstraction to separate language-model integration from the core application logic.

### Anthropic Provider

When configured, the Anthropic adapter performs model calls and maps provider errors into application-level error types.

### Rule-Based Demo Provider

The rule-based provider supports demonstrations without a model API key. It uses limited pattern-based extraction and is intended for controlled demonstrations and deterministic testing.

**Important:** The rule-based provider should not be treated as evidence of general natural-language understanding. Live-model behavior should be evaluated separately.

## 7. Session Handling and Limitations

The application maintains session state in an in-memory backend repository. The frontend stores the session identifier in browser local storage to support resuming a session while the corresponding backend session remains available.

Because the backend repository is in memory, sessions may be lost when the application restarts.

The application does not implement authentication or authorization. It is a technical demonstration and should not be treated as a production system for sensitive personal information.

## 8. Testing

The project includes backend and frontend tests for application behavior, validation, state transitions, and user-interface functionality.

The repository's README and test reports should be consulted for the latest test counts and execution results. Test-suite results do not, by themselves, establish the accuracy of a live language model.

## 9. Documentation Index

See the other files in the `docs/` directory for more detail:

- `ARCHITECTURE.md` — application components and their interactions.
- `VALIDATION_AND_STATE.md` — field states, validation, and state transitions.
- `API_REFERENCE.md` — HTTP endpoints, request and response behavior, and error handling.
- `TESTING.md` — testing approach and available evidence.
- `VIDEO_WALKTHROUGH.md` — walkthrough information, if available.
- `Evaluator_Guide_Final.pdf` — evaluator-facing overview and technical handoff.

## 10. Scope and Safety Disclaimer

This application generates a fictional Personal Wishes Document draft for demonstration purposes only.

It does not provide legal advice, verify legal facts, or create a legally valid document. Users should not rely on its output as a substitute for professional legal guidance.

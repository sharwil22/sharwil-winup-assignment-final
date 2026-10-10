# PRD — Document Intake Assistant

_Wenup engineering technical test · as of 2026-10-07_

## Summary

We will build the **Document Intake Assistant**: a chat app that interviews a user, keeps a validated structured record of their answers, and renders a draft fictional _Personal Wishes Document_ from that record. The core design rule is **the LLM proposes, the application decides**. The model only suggests field updates. Deterministic code validates them, applies them to the state, chooses what to ask next and generates the document.

The brief grades engineering judgement over feature count. It asks for:

- A backend and a simple UI with a multi-turn chat, a live preview of the structured state and the draft document, and the ability to correct earlier answers.
- An explicit schema as the source of truth, not the chat history.
- Reliable LLM behaviour: sensible follow-ups, no invented facts, explicit unknowns, no repeated questions, several fields per answer in any order.
- Validation of model output, clear layer separation, a defined API contract, graceful error handling, meaningful tests, simple local setup, secrets out of source control.
- A public Git repo with setup instructions, an AI log and a short production-improvements note. A deterministic mock LLM is acceptable.

Related documents: [TRD](TRD.md) · [Implementation Plan](IMPLEMENTATION_PLAN.md) · [Step by Step](STEP_BY_STEP.md)

## Problem and goal

Form-filling for personal documents is tedious, but a free-form chatbot cannot be trusted to keep facts straight. The product goal is a conversation that feels natural while every captured fact stays explicit, checkable and correctable. Success for this exercise is a reviewer seeing reliable state handling around an LLM, not legal sophistication.

## Users

| User | Need |
| --- | --- |
| End user (fictional applicant) | Answer questions in plain language, see what was understood, fix mistakes, get a readable draft |
| Wenup reviewer | Run it locally in minutes, read clear code and tests, understand the decisions from the README and AI log |

## Information to collect

| Field | Type | Rule |
| --- | --- | --- |
| Full name | text | Required |
| Home address | text | Required; a partial address is flagged as unclear |
| Covers worldwide assets | yes / no | Required; must be an explicit answer, never assumed |
| Has children | yes / no | Required |
| Children's names | list of text | Required only if has children = yes; otherwise not applicable |
| Executor name | text | Required |
| Executor relationship | text | Required; can be inferred only when stated ("my brother James") |
| Specific gifts | list of {item, recipient} | Optional; the user may say "none" |
| Additional wishes | text | Optional; the user may say "none" |

Every field also carries a status: **missing**, **needs clarification**, **captured**, or **not applicable**. Optional fields count as complete only once the user has answered them, including with "none".

## User stories

1. As a user, I can start an interview and the assistant asks one clear question at a time.
2. As a user, I can answer several things at once ("I'm Jane Smith, 4 High St, Leeds, no kids") and all of them are captured.
3. As a user, I can answer in any order, and the assistant does not ask again for what it already has.
4. As a user, when my answer is vague or contradicts an earlier one, the assistant asks a specific follow-up instead of guessing.
5. As a user, I can correct an earlier answer in chat ("actually my executor is my sister Anna") and the preview updates.
6. As a user, I can also edit a field directly in the preview panel.
7. As a user, I see a live panel of captured fields with their status, and a live draft document.
8. As a user, I can see the draft is clearly labelled fictional and not legal advice.
9. As a user, if the AI service fails, I get a clear message and my captured answers are not lost or corrupted.

## Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | Multi-turn chat between user and assistant | Must |
| FR-2 | Explicit schema is the single source of truth; chat history is context only | Must |
| FR-3 | Extract zero, one or many field values from each user message | Must |
| FR-4 | Never record a value the user did not state; unknowns stay explicitly missing | Must |
| FR-5 | Ask a targeted follow-up for missing, unclear or contradictory answers | Must |
| FR-6 | Never re-ask a field that is already captured, unless clarifying a conflict | Must |
| FR-7 | Corrections in chat overwrite the earlier value and are shown as a change | Must |
| FR-8 | Validate every model output before it touches state; reject invalid updates | Must |
| FR-9 | Live preview of state and document, always rendered from the latest state | Must |
| FR-10 | Deterministic document generation with a fictional / not-legal-advice banner and visible placeholders for gaps | Must |
| FR-11 | Clear errors for model failure, malformed output and missing configuration; state unchanged on failure | Must |
| FR-12 | Mock LLM provider usable with no API key | Must |
| FR-13 | Direct field editing in the preview panel | Should |
| FR-14 | Interview-complete state with a final review prompt | Should |
| FR-15 | Download the draft as Markdown | Could |

## Non-goals

- Real legal validity, jurisdiction rules or legal advice.
- User accounts, authentication or multi-user persistence.
- Production hosting, scaling or compliance work (covered only in the production note).
- PDF or Word export, signatures, witnesses.

## Success criteria

- A reviewer goes from clone to a working chat in under 5 minutes, with or without an API key.
- The scripted demo conversations (multi-field answer, correction, contradiction, vague answer, malformed model reply) all behave as specified.
- Automated tests pass and cover state updates, validation, corrections, error handling and document generation.
- The README, AI log and production note explain the key decisions candidly.

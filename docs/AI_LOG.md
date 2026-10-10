# AI Log

How AI tools were used to build this project: key prompts, notable iterations, and output I questioned or corrected. Kept short and candid.

## How I worked

- **Tool:** Claude Code (in VS Code) for planning, implementation, tests and documentation. When it wrote the Claude API adapter, it used Anthropic's bundled API reference, not memory.
- **Process:** I had it write a PRD, TRD and step-by-step plan from the brief first, then build one phase at a time. Each phase ended with tests, lint, a commit, and an entry in the build journal ([docs/BUILD_JOURNAL.md](docs/BUILD_JOURNAL.md)) explaining what was done and why.
- **Checking the output:** every phase was gated on tests, ruff, strict mypy, oxlint and tsc. Beyond that, the most useful checks were reading the actual output (the rendered document, the server log) and driving the real UI in a browser. Those found problems the tests didn't.

## Key prompts

| Prompt (short) | Purpose |
| --- | --- |
| "Read the attached brief and write a PRD, TRD and implementation plan" | Requirements and design before code |
| "Split them into three Markdown files, plus a step-by-step build file" | A plan to follow and check against |
| "Start Phase 1" … "continue" (per phase) | Build in small, verifiable steps |
| "As you build, keep an MD file of what we did and how, so I can explain it in an interview" | The build journal |

The prompt the **application** sends to Claude is in [backend/app/llm/prompts.py](backend/app/llm/prompts.py) (versioned as `PROMPT_VERSION`). It went through two design changes: the `clarifications` list was removed and `asks_about` was added (see Phase 4 below).

## Output I questioned or corrected

The most important ones, in the order they happened:

1. **Unclear answers could overwrite confirmed ones.** The first design stored one value per field. Added a separate `candidate` slot so a vague or contradictory answer is held for clarification without touching the confirmed value.
2. **Over-clever code.** A validation helper returned errors as a subclass of `str`. Replaced it with a plain dataclass, because readability matters more than brevity.
3. **Over-aggressive escaping.** The first document generator escaped every punctuation mark, so `4 High St.` became `4 High St\.` in the downloaded file. Narrowed it to the characters that can actually change Markdown structure.
4. **A weak test.** A regex test meant to prove "no invented names" flagged the template's own heading. Removed it in favour of snapshot tests plus explicit checks.
5. **An outdated API pattern.** The TRD planned a forced tool call for structured output. Checking the current Claude API before writing the adapter showed that current models reject forced `tool_choice`. Switched to structured outputs (JSON schema), still validated by our own Pydantic contract. The default model also changed from Sonnet to `claude-opus-5-5`; it stays configurable.
6. **A redundant contract field.** Dropped the model's separate `clarifications` list (already covered by `certainty: "unclear"`). Added `asks_about`, so checking "does the reply ask about a captured field?" is an equality check, not text parsing.
7. **Conflict detection on the wrong version.** Moved from the state version to a session version, because a turn that changes no field still adds messages.
8. **A test that passed by accident.** An API test passed on the first run. Re-reading it showed the demo provider had stored "My brother James" as the user's *full name*; the test only checked a later step. Rewrote it.
9. **Six UI issues the unit tests missed**, found by driving the app in headless Chrome and reading screenshots:
    - two sessions created per page load (React StrictMode runs effects twice in development);
    - the whole page scrolled on each message;
    - field labels in Title Case;
    - a double "thank you" at the end;
    - "Thanks, I've noted that." after a vague answer that wasn't recorded;
    - no follow-up question after a panel edit reopened a field.
10. **A suspected bug that wasn't one.** A screenshot showed a nearly empty progress bar at 7 of 9. Measuring it showed the CSS transition had been caught mid-animation. No change made.

Also caught, but in tooling rather than the app: a demo-provider regex that was case-sensitive ("My brother" vs "my brother"), Node 25's experimental `localStorage` breaking the jsdom tests, a shell `echo` mangling JSON in a smoke test, and a browser-automation script waiting on the wrong selector.

## Per-phase log

| Phase | Prompt (short) | What came back | Kept / changed, and why |
| --- | --- | --- | --- |
| Plan | "Read the brief and write a PRD, TRD and implementation plan" | Design rule "the LLM proposes, the application decides"; docs in `docs/` | Kept the design. Asked for split Markdown files plus a step-by-step guide |
| 1. Setup | "Start Phase 1" | Repo, backend/frontend skeletons, config, health endpoint, Makefile | Kept as is |
| 2. Domain | "Continue" | State model, validation, reducer, planner, 55 tests | Added the `candidate` slot (1); replaced the `str`-subclass helper (2). Mypy over the tests caught a stray `type: ignore` |
| 3. Document | "Continue" + "keep a build journal" | Jinja2 generator, snapshots, 15 tests; build journal | Escaping narrowed (3); weak test removed (4); executor sentence reworded after reading the output |
| 4. LLM | "Continue" | Contract, prompt, Claude adapter, mock providers, turn pipeline, 12 fixtures, 63 tests | Structured outputs instead of forced tool use, model default (5); contract simplified (6); a test caught the regex case bug |
| 5. API | "Continue" | Session store, service layer, 6 endpoints, error envelope, 24 API tests | Session version (7); rewrote the accidental pass (8) |
| 6. UI | "Continue" | React UI, `useSession` hook, 14 component tests, browser walkthrough | Six fixes from using the real app (9); ruled out a false alarm (10) |
| Design | "Make the UI look professional like PayPal and Razorpay" + "make the chat like iMessage" | Token-based redesign: navy top bar, cards, pill badges, paper-sheet document, Messages-style chat with bubble tails | Kept to visual cues only (no brand names, logos or colours, to avoid imitating those companies). Screenshots found two issues: an avatar icon that read as a loading spinner (now initials) and misaligned status chips on rows without an edit button |
| Audit | "Test everything against the PDF; add something unique" | Compliance report, two new eval scenarios, `--repeat`, browser walkthrough with Claude, answer-provenance feature | The repeated live eval exposed a real gap: Claude sometimes asked about a contradiction without proposing the conflicting value, so the app recorded nothing and replaced its question. Diagnosed from the raw model output, fixed with one prompt rule (contradictions must be proposed, never resolved by the model). Also fixed "I leave car to Tom" wording |
| Video | "Make an MD file with a video explaining the project, the approach, the process and the technical terms" | 3:20 narrated video (HyperFrames, local Kokoro voice, word-synced beats, 2× app screenshots) + `docs/VIDEO_WALKTHROUGH.md` | Review found run-together headline words (whitespace collapsed between animated spans), a clipped document zoom, a final fade aimed at a missing element, and a title colliding with its subtitle; all fixed. On request, removed mentions of the planning documents and re-voiced that scene |
| 7. Hardening | "Continue" | `make eval` (6 scenarios), README, production notes, this log, clean-clone check | The eval immediately showed the demo provider's limits (it stores "Just call me Jane" as the full name). Kept as an honest demonstration of what the eval is for |

## Verified against Claude

`make eval` with `claude-opus-5-5` at low effort: **6/6 scenarios pass** (multi-field, "my brother James", correction, contradiction, vague address, no invented surname), no replies replaced by the planner, no malformed-output fallbacks, about 3–5 s per turn.

Using the real UI with Claude found one more issue: the "Next:" hint (added for direct edits) also appeared after normal chat turns, repeating the question Claude had just asked in its own words. Its check compared the planner's exact wording with the model's. Fixed by showing the hint only after an edit in the panel, and added a test.

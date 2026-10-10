# AI Usage Log

**Document Intake Assistant · Wenup engineering technical test**

|  |  |
| --- | --- |
| **Document** | AI Usage Log: prompts, iterations and corrected output |
| **Version** | 1.0 |
| **Date** | 10 October 2026 |
| **Source repository** | [github.com/sharwil22/sharwil-winup-assignment-final](https://github.com/sharwil22/sharwil-winup-assignment-final) |
| **Related documents** | Evaluator Guide and Technical Overview; [Production Improvements](PRODUCTION_NOTES.md) |

## 1. Summary

I used an AI coding assistant throughout the project: to turn the brief into a written plan, to implement the application one phase at a time, and to write tests and documentation. Every phase was gated on automated checks, and I reviewed the output against the brief, the running application and the live model. This log records the prompts that shaped the work, the iterations that changed it, and the output I questioned or corrected.

| Aspect | Detail |
| --- | --- |
| Assistant | Claude Code (Anthropic), used in VS Code |
| Working method | Written plan first, then seven build phases; each phase ended with passing tests, static checks and a commit |
| Verification gates | pytest, Vitest, ruff, mypy (strict), oxlint, tsc; browser walkthroughs of the running app; a live evaluation against Claude |
| Corrections recorded | 12 significant corrections to AI output (Section 5), plus 7 defects found only by running the real system (Section 6) |
| Final state | 155 backend and 15 frontend tests pass; live evaluation 8 of 8 scenarios on 3 of 3 runs each |

## 2. How AI was used

| Activity | AI contribution | My role |
| --- | --- | --- |
| Requirements and design | Drafted product and technical requirements and a phased plan from the brief | Set the core design rule, reviewed scope, asked for a step-by-step plan to check work against |
| Implementation | Wrote backend, frontend and test code phase by phase | Directed each phase, reviewed output, rejected or reworked code that was unclear or wrong |
| Model integration | Wrote the Claude adapter using Anthropic's current API reference rather than recalled patterns | Approved the change of approach when the reference showed the planned method was no longer supported |
| Verification | Ran test suites, static checks, browser automation and the live evaluation; produced screenshots for review | Reviewed results and screenshots; decided what counted as a defect |
| Documentation | Drafted the README, evaluator guide, build journal and this log | Edited for accuracy and audience; removed claims that could not be verified |

## 3. Working method

1. **Plan before code.** The brief was turned into written requirements and a phased plan, so each step had a definition of done.
2. **Small, verifiable phases.** Setup, domain rules, document generator, model layer, API, interface, hardening. No phase started until the previous one passed its checks.
3. **Automated gates.** Every phase ended with the full test suites and strict static analysis passing, and a commit.
4. **Checks beyond unit tests.** I read the actual output (rendered documents, server logs, raw model responses) and drove the running interface in a browser. These checks found defects the unit tests did not (Section 6).
5. **Live-model evaluation.** Scripted conversations against Claude, repeated several times, because a single passing run says little about model behaviour.
6. **Decision record.** A build journal recorded what was built in each phase, why, and what changed along the way.

## 4. Key prompts

| # | Prompt (abridged) | Intent | Outcome |
| --- | --- | --- | --- |
| P1 | "Read the attached brief and write a PRD, TRD and implementation plan." | Establish requirements and architecture before writing code | Design rule adopted: the model proposes, the application decides |
| P2 | "Split these into separate Markdown files, and add a step-by-step build guide." | A plan that each phase can be checked against | Four planning documents |
| P3 | "Start Phase 1", then "Continue" for each phase | Build in small increments with a review point after each | Seven phases, each with tests and a commit |
| P4 | "As you build, keep a file of what we did and how, so the work can be explained in detail." | A record of decisions and their rationale | Build journal maintained throughout |
| P5 | "Make the interface look professional, in the style of a payments dashboard; make the chat look like iMessage." | Raise visual quality for reviewers | Redesigned interface using visual cues only; no third-party branding |
| P6 | "Test everything against the brief and add a distinctive feature." | Independent compliance check | Compliance audit, two new evaluation scenarios, answer-provenance feature, one real defect found and fixed |
| P7 | "Produce documentation and a video that explain the project, the approach and the technical terms." | Make the work reviewable without reading all the code | Evaluator guide, narrated walkthrough, glossary |

### 4.1 The application's own prompt

The prompt the application sends to Claude is kept in `backend/app/llm/prompts.py` and versioned with `PROMPT_VERSION`, which is written to the logs on every model call. It changed three times during development:

| Change | Reason |
| --- | --- |
| Removed a separate `clarifications` list from the contract | Redundant with `certainty: "unclear"` on each update; fewer fields means less for the model to get wrong |
| Added `asks_about` | Lets the server check whether the reply targets the right field with an equality test instead of parsing free text |
| Added rule 10 (version `2026-10-07.2`) | Contradictions must be proposed as updates, never resolved by the model; see correction C11 |

## 5. Output questioned or corrected

Significant points where AI-produced work was challenged, in the order they occurred.

| # | Area | What was produced | Problem and decision |
| --- | --- | --- | --- |
| C1 | State model | One value per field | An unclear or contradictory answer could overwrite a confirmed one. Added a separate `candidate` slot so uncertain answers wait for clarification without touching confirmed data. |
| C2 | Validation | Errors returned as a subclass of `str` | Clever but hard to read. Replaced with a plain dataclass. |
| C3 | Document generator | Escaped every punctuation mark | `4 High St.` became `4 High St\.` in the downloaded file. Narrowed escaping to characters that can change Markdown structure. |
| C4 | Tests | Regex test for "no invented names" | Matched the template's own heading, so it proved nothing. Replaced with snapshot tests and explicit assertions. |
| C5 | Model adapter | Planned a forced tool call for structured output | Anthropic's current API reference showed current models reject forced `tool_choice`. Switched to structured outputs with a JSON schema, still validated by our own contract. |
| C6 | Model contract | Separate `clarifications` list | Redundant; removed. Added `asks_about` (Section 4.1). |
| C7 | Concurrency | Conflict detection on the state version | A turn that changes no field still adds messages, so a stale client could slip through. Moved to a session version. |
| C8 | Tests | An API test that passed on its first run | On review it passed by accident: the demo provider had stored "My brother James" as the user's full name. Rewrote the test to set up the state it intended. |
| C9 | Interface design | A redesign that referenced named brands | Kept to visual cues only, with no third-party names, logos or colours, to avoid imitating other companies. |
| C10 | Draft wording | "I leave car to Tom." | The model sometimes stores an item without "my". The template now adds it unless the item already starts with a determiner or possessive. |
| C11 | Contradiction handling | Prompt allowed the model to ask about a contradiction without proposing the conflicting value | The application recorded no conflict and replaced the model's question, so the follow-up was lost. Diagnosed from the raw model output; fixed with prompt rule 10. Verified on 5 of 5 targeted runs, then 3 of 3 in the full evaluation. |
| C12 | Documentation | An evaluator guide referencing files and figures | Checked against the published repository; references to files not in the repository were removed, and test counts were verified rather than quoted. |

## 6. Defects found by running the real system

All automated tests passed before these were found. Each was found by driving the running application in a browser or by running the live evaluation, then fixed and covered by a test where possible.

| # | Defect | Cause and fix |
| --- | --- | --- |
| D1 | Two sessions created on every page load | React StrictMode runs effects twice in development; added a load-once guard |
| D2 | Whole page scrolled when a message arrived | `scrollIntoView` scrolls every ancestor; now scrolls only the chat log |
| D3 | Final reply thanked the user twice | Acknowledgement and completion message were concatenated; acknowledgement removed at completion |
| D4 | "Thanks, I've noted that." after a vague answer that was not recorded | Acknowledgement now appears only when a value is actually captured |
| D5 | No follow-up question after a panel edit reopened a field | Added a "Next" prompt from the server's next question |
| D6 | "Next" prompt repeated a question the model had just asked in its own words | Prompt restricted to panel edits only; test added |
| D7 | Contradictions sometimes dropped by the live model | See C11 |

Also investigated and ruled out: a progress bar that appeared nearly empty in one screenshot was a CSS transition captured mid-animation; measurement confirmed the correct value.

## 7. Decisions I made

- The central design rule: the model only proposes; deterministic code validates, applies, plans and renders.
- Rendering the document from a template rather than from model text, accepting less natural prose in exchange for a draft that can only contain confirmed answers.
- Requiring every extracted value to quote the user's own words, accepting that some correct paraphrases are rejected and asked again.
- Adding answer provenance so each value visibly traces back to the user's words.
- Keeping the offline rule-based provider as the default for local runs, so the application can be reviewed without an API key.
- Not claiming in documentation anything that could not be verified against the repository or the running system.

## 8. Verification summary

| Check | Result | Notes |
| --- | --- | --- |
| Backend tests (pytest) | 155 passed | Domain, interview pipeline, provider adapter, document, API |
| Frontend tests (Vitest) | 15 passed | Against an in-memory fake backend |
| Static analysis | Clean | ruff, mypy (strict), oxlint, tsc |
| Live evaluation (Claude) | 8 of 8 scenarios, 3 runs each | `claude-opus-5-5`, low effort, prompt version `2026-10-07.2` |
| Browser walkthrough | No console errors | Full interview, correction, contradiction, panel edit, document download |
| Clean-clone setup | Running in 18 s | With empty package caches |

## 9. Reflections

- AI was most valuable for speed and breadth: scaffolding, test coverage and documentation that would otherwise take much longer.
- Its output needed the most scrutiny where it was confident and plausible: an outdated API pattern, a test that passed for the wrong reason, a design that allowed a guess to overwrite a confirmed fact.
- Unit tests were necessary but not sufficient. Reading real output, using the real interface and repeating live-model runs found every defect in Section 6.

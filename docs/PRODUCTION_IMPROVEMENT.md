# Production Improvements

**Document Intake Assistant · from prototype to production service**

| | |
| --- | --- |
| **Document** | Production Improvements: gaps, priorities and plan |
| **Version** | 1.0 |
| **Date** | 10 October 2026 |
| **Applies to** | Branch `main` as deployed on Render (single web service, in-memory sessions) |
| **Related documents** | Evaluator Guide and Technical Overview; [AI Usage Log](AI_LOG.md) |

## 1. Summary

The current build is a prototype for an engineering exercise. Its core design is suitable for production: domain rules are isolated from storage, the model provider and HTTP, so each improvement below is a contained change rather than a rewrite. Before real people's information is handled, the priority is data protection, identity and durable storage; model-quality and operational work follow.

### 1.1 Current state against production target

| Area | Current state | Production target |
| --- | --- | --- |
| Data protection | Fictional data; logs contain ids and counts, not message text | Personal data handled under a documented assessment, with encryption, retention and deletion |
| Identity and access | No authentication; a session id grants access to that session | Authenticated users who own their sessions; authorisation on every route |
| Storage | In-memory repository; lost on restart or redeploy | Postgres with the same optimistic versioning, backups and an audit trail |
| Model quality | 8 scripted scenarios run on demand | Labelled evaluation set run in CI on every prompt or model change |
| Operations | Basic logs; health endpoint | Tracing, error tracking, alerting and cost monitoring |
| Hosting | Single free-tier instance that sleeps when idle | Always-on instances across environments, with secrets in a secrets manager |
| Legal content | One fictional template | Jurisdiction-specific templates reviewed by qualified professionals |

## 2. Prioritised improvements

P0 items are required before any real user. P1 items are required for a reliable service. P2 items improve quality and reach. Effort is indicative: S (days), M (one to two weeks), L (several weeks).

| ID | Priority | Improvement | Rationale | Effort |
| --- | --- | --- | --- | --- |
| 1 | P0 | Data protection assessment, encryption, retention and deletion | The data is sensitive: names, addresses, family details and wishes | M |
| 2 | P0 | Authentication and per-session authorisation | A session id alone is not access control | M |
| 3 | P0 | Durable storage (Postgres) with audit trail | Sessions must survive restarts; changes must be attributable | M |
| 4 | P0 | Secrets in a secrets manager; secret scanning in CI | No credential should be committable or visible in configuration files | S |
| 5 | P0 | Model-provider data agreement and user disclosure | User answers are processed by an external AI service | S |
| 6 | P1 | Rate limiting and request size limits per user | Each message triggers a paid model call | S |
| 7 | P1 | Evaluation suite in CI with regression gates | Prompt or model changes must not silently reduce accuracy | M |
| 8 | P1 | Observability: tracing, error tracking, alerting | Failures and cost must be visible without logging personal data | M |
| 9 | P1 | Always-on hosting, separate environments, automated deployment | The free tier sleeps; changes need a staging environment | S |
| 10 | P1 | End-to-end browser tests in CI | Manual browser runs found defects that unit tests missed | M |
| 11 | P2 | Streaming replies | Turns currently wait 3 to 5 s for the full validated response | S |
| 12 | P2 | Final review and confirmation step | Explicit user sign-off on every field before a document is produced | S |
| 13 | P2 | Jurisdiction-specific templates with legal review | Real documents have legal requirements the fictional draft ignores | L |
| 14 | P2 | Accessibility audit, additional languages, PDF and Word export | Reach and usability | M |

## 3. Detailed changes

### 3.1 Security and data protection

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Data protection impact assessment | Classify all fields as personal data; record lawful basis, processors and retention | Assessment signed off before launch |
| Encryption | TLS for all traffic; encryption at rest for the database and backups | Verified in configuration review |
| Retention and deletion | Defined retention period; user-initiated deletion that reaches backups and logs | Deletion request removes all copies within the stated period |
| Logging discipline | Logs keep ids, counts and warning codes only; enforced by a test or log scrubber | No message text or field values in any log |
| Secrets management | Keys held in a secrets manager; `.env` files never committed; secret scanning on every push | CI fails on any committed credential |
| Model provider terms | Data processing agreement, zero data retention where available, region pinning if required | Agreement in place; disclosure shown to users |

### 3.2 Identity and access

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Authentication | Passwordless email or single sign-on | Every API route requires an authenticated user |
| Session ownership | Sessions linked to a user; ownership checked on every read and write | Accessing another user's session returns 404 |
| Abuse controls | Rate limits per user and per IP on the message endpoint; existing 2,000-character message limit retained | Limits enforced and covered by tests |

### 3.3 Persistence

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Postgres repository | Implement the existing `SessionRepository` interface; a `version` column with `UPDATE … WHERE id = ? AND version = ?` preserves optimistic concurrency | Existing API tests pass unchanged against Postgres |
| Audit trail | Append-only table of field changes: field, old and new value, source (chat or edit), turn, time | Every confirmed value traceable to its change |
| Operations | Schema migrations, automated backups, scheduled restore drills | Restore drill completed successfully |

### 3.4 Model quality and safety

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Evaluation in CI | Grow the 8 scripted scenarios into a labelled set of real, consented and anonymised conversations; score field accuracy, invented facts, re-asks and clarification rate | Prompt or model changes blocked on regression |
| Prompt traceability | Store `PROMPT_VERSION` and model id with every turn | Any behaviour traceable to a prompt version |
| Quality monitoring | Track rates of rejected updates, malformed output, refusals and replaced replies per prompt version and model | Alert on significant change |
| Cost and latency | Prompt caching for the static system prompt; budget alerts; evaluate lower effort or a smaller model where quality holds | Cost per completed interview tracked against a budget |
| Prompt injection | Keep user text fenced as data. The structural defence remains: the model only proposes, and values must quote the user's words | Injection test cases in the evaluation set |

### 3.5 Reliability and operations

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Health and readiness | Readiness checks include the database and the model provider | Unready instances receive no traffic |
| Tracing and error tracking | Request ids across API, service and model call; error tracking with personal data scrubbed | Any failed request traceable end to end |
| Hosting | Always-on instances, separate staging and production, automated deployment from CI | No cold starts in production |
| Graceful degradation | When the model is unavailable, users can continue with direct field editing (already supported) and are told so | Clear message; no data loss |

### 3.6 Product and legal

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Legal templates | Jurisdiction-specific templates, required clauses, witnessing and signing rules, reviewed by qualified people. Because the document is template-based, this is a content change, not an engineering one | Templates approved and versioned |
| Final confirmation | Read-back of every answer with explicit confirmation before the document is produced | No document without confirmation |
| Accessibility and reach | WCAG 2.2 AA audit; additional languages with validated rules per language; PDF and Word export with the disclaimer preserved | Audit passed; exports tested |

### 3.7 Engineering process

| Change | Detail | Acceptance criterion |
| --- | --- | --- |
| Continuous integration | Lint, type checks, unit tests, build and dependency scanning on every pull request; evaluation on a schedule | Main branch protected by required checks |
| Generated API types | Generate frontend types from the OpenAPI schema instead of maintaining them by hand | Type drift caught at build time |
| End-to-end tests | Playwright tests for the main journeys: interview, correction, contradiction, edit, download | Run in CI on every pull request |

## 4. Phased plan

| Phase | Scope | Exit criterion |
| --- | --- | --- |
| Phase 0: Foundations | Items 1 to 5 (data protection, authentication, Postgres, secrets, provider agreement) | Safe to handle real personal data for a closed pilot |
| Phase 1: Reliable service | Items 6 to 10 (rate limits, evaluation in CI, observability, hosting, end-to-end tests) | Service level and model quality measured and monitored |
| Phase 2: Product maturity | Items 11 to 14 (streaming, confirmation step, legal templates, accessibility and exports) | Ready for general availability in the first jurisdiction |

## 5. Risks and trade-offs

| Risk or trade-off | Mitigation |
| --- | --- |
| Model behaviour changes with a new model version | Pin model versions; gate upgrades on the evaluation suite |
| Evidence checking rejects some correct paraphrases | Accepted by design: the user is asked again. Monitor the rejection rate and refine prompts against the evaluation set |
| Template-based documents read less naturally than generated prose | Accepted by design: the draft can only contain confirmed answers. Wording improves through template revisions |
| Model cost grows with usage | Prompt caching, rate limits, budget alerts and effort tuning measured against the evaluation |
| External provider outage | No data is lost (nothing is saved on failure); direct editing remains available; consider a secondary provider behind the existing interface |

The application produces a fictional document for an engineering exercise. It must not be used to create real legal documents before the legal work in Section 3.6 is complete.

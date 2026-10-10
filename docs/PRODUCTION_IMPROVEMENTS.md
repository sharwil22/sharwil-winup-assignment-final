# Production Improvements

This project is a prototype for collecting personal wishes and generating a fictional draft. Before offering it to real users, I would make the following improvements, in priority order.

## 1. Protect personal information

The interview may contain names, addresses, family relationships, and personal wishes. I would treat all of this as sensitive data. Before launch, I would complete a privacy impact assessment, explain clearly what data is collected and how any AI provider processes it, and confirm that the provider's terms and data-handling settings meet the product's privacy requirements.

I would encrypt traffic using TLS and encrypt stored data and backups. I would define a retention period, provide users with a straightforward way to delete their sessions and exported data, and ensure deletion also applies to backups according to a documented schedule. Logs, analytics, and error reports should not contain message text or other personal details; I would add automated checks to help prevent accidental exposure.

## 2. Add identity, access control, and durable storage

Sessions are currently held in memory, so they can be lost when the service restarts, and a session identifier should not be treated as proof of a user's identity. I would add authentication and authorize every request so users can access only their own sessions. I would replace the in-memory repository with a managed database, use schema migrations, and retain the existing optimistic-concurrency behavior to avoid overwriting newer edits.

I would also create an append-only audit history for changes to important fields, recording when a change happened and whether it came from chat or a user edit. Access to the database and audit records would be restricted, and backups would be encrypted and regularly tested through restore drills.

## 3. Strengthen AI quality and operational safeguards

The current evaluation set is useful for development but too small to establish production reliability. I would expand it with consented, anonymized examples covering ambiguous answers, corrections, contradictions, unusual phrasing, and attempts to introduce unsupported facts. I would measure extraction accuracy, unsupported-update rates, clarification behavior, and whether the system asks questions about fields that are still open. I would run these evaluations whenever the prompt or model changes and block releases that introduce meaningful regressions.

In production, I would monitor model errors, rejected updates, malformed responses, latency, and cost without logging personal conversation content. I would add request IDs and tracing across the API, interview service, and model call, plus alerts for unusual error or rejection rates. I would enforce rate limits and request-size limits, set usage budgets, and make model outages clear to users while preserving their confirmed data.

## 4. Review the document and user experience

The generated document is explicitly fictional and is not legal advice. Before supporting real legal documents, I would have qualified legal professionals review the content, required clauses, jurisdiction-specific rules, and any signing or witnessing instructions. I would version approved templates and make the app clearly identify which version generated a document.

Before export, I would add a final review step that lets users confirm each field and correct errors. I would also conduct accessibility and usability testing, especially around clarification, editing, and communicating the limits of AI-generated drafts.

## Summary

My first production priorities would be privacy and access control, because the application handles sensitive personal information. Next, I would establish reliable storage and backups, prove model behavior with broader evaluations and monitoring, and obtain professional review before presenting any document as legally meaningful.

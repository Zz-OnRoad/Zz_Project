---
name: reply-rules
description: Structure complex-task collaboration replies with CTHP, including initial framing, progress or status updates, decision requests, evidence summaries, and final handoffs. Use when the current task has multiple stages, branches, deliverables, repeated or consequential tool calls, external actions, long-running work, multi-agent collaboration, or elevated risk. Continue using it on later follow-up turns belonging to an active complex task—even when the message is brief—for status checks, added requirements, branch decisions, exception handling, and handoff. Do not use for independent simple one-step questions or merely because one low-risk tool call is needed.
---

# Reply Rules

## Apply CTHP

1. Read [references/core-protocol.md](references/core-protocol.md) completely before composing an applicable user-facing reply.
2. Classify the current reply and read the matching reference completely:
   - Initial framing, milestone update, status heartbeat, or changed task snapshot: [references/progress-updates.md](references/progress-updates.md)
   - User decision, approval checkpoint, or authorized interruption: [references/decision-requests.md](references/decision-requests.md)
   - Final handoff, partial handoff, blocked handoff, or audit-style closeout: [references/final-handoffs.md](references/final-handoffs.md)
3. If one reply combines types, read every applicable reference. Do not load unrelated modules merely for completeness.
4. Apply the protocol to the collaboration wrapper around the work. Preserve the requested deliverable in its complete, appropriate form.

Do not mechanically add every field, table, or heading. Use only the structures required by the current task, while always preserving material failures, risks, unknowns, external effects, and user decisions.

# Ticket acceptance and automatic scoring

Implemented 2026-11-10. This amendment supersedes earlier descriptions of
recursive target budgets and automatic same-task hard-failure penalties.
Planner skill slicing guidance remains a separate, deferred change.

## Evidence contract

Code defaults to `EVIDENCE: CHANGED`: require new or meaningfully modified
permanent `tdd_cases`, then execute the complete hot suite, task VERIFY and
scope/audit checks before committing. LEVEL never bypasses these checks.

Only an explicit `[CODE: REFACTOR]` ticket may select `EVIDENCE: EXISTING`.
It must pin nonempty `CASES: id,id`. Each case must exist at the baseline,
have an unchanged discovered fingerprint and a tracked, nonignored source,
and execute successfully with matching source/fingerprint in full hot.
Worker result fields cannot select this exception. Existing scope, assertion
and deletion guards remain active; this mode does not authorize behavior changes.

`[VERIFY]` tickets require an executable VERIFY command and `outcome=no_change`.
Runtime executes the command and records bounded actual evidence, rejects
nonzero exits and recognized zero-test runs, and checks for product edits before
and after verification. No-change results need a reason. They create no commit
and earn no development score credit. Generic wrappers normalize no_change to
the protocol's complete execution status while retaining the result outcome.

Invalid EVIDENCE, FILES, LEVEL or VERIFY contracts block before queue removal or
model invocation. `CONTRACT_BLOCKED` preserves the queue and score; Sentinel
relays it to Planner through the existing blocked event. Correct the ticket
to let normal polling retry it.

## Planned budget

`planned_files = max(1, unique TARGET entries, FILES)`; FILES is optional and
must be a positive integer. Directory contents are never recursively counted.
Code action budget is `max(step_base[LEVEL], preparation_steps) +
planned_files * STEP_PER_FILE`. The preparation floor defaults to step_base.L2;
an explicit worker.preparation_steps must be a positive integer.
With 60/40/20 bases and five steps per file, one-file L1/L2/L3 budgets are
65/45/45. Research retains its independent budget. Runtime-owned hot uses wall
time rather than Worker actions; the floor covers Worker preparation/closeout,
and does not remove phase deadlines.

## Automatic feedback

Every two consecutive attributable failures reduce the executing registration's
score by one, including across different task IDs. Five effective development
accepts increase it by one. Score stays within 1..5. An accept resets the failure
streak; an attributable failure clears the accept window. Neutral outcomes
affect neither window. Event identities prevent replay from applying feedback
twice. Crossing a recommended LEVEL threshold emits the existing capability
event and holds dispatch for Planner acknowledgement.

Attributable evidence includes proven ticket regressions, productive agent
timeouts/action exhaustion and explicit scope/audit violations. Baseline failures,
environment/contract blocks, unsupported evidence, hot timeouts, unproven task
VERIFY failures and unknown causes stay neutral. Research and verification-only
outcomes are neutral. Candidate traceback remains primary when baseline
isolation is unsupported or incomplete; classification limitations are separate.
Reports persist score_attribution with category, phase and attribution flag.

Existing scores/history are preserved. Missing attributable_failure_streak
starts at zero; old failures are not reinterpreted. Legacy score-record accept,
reject, success, no_fault and hard_failure remain supported; hard_failure retains
its historical same-task attempt-2/3 arithmetic for explicit callers. Automatic
lifecycle feedback now uses attributable_failure instead. Planner continues to
read the registration score directly; no additional capacity-review step exists.

Regression evidence: test_ticket_granularity covers real Git/daemon handoffs,
strict versus existing evidence, preclaim refusal, real VERIFY, budget estimates,
cross-ticket penalties, replay, neutral outcomes and score recovery.

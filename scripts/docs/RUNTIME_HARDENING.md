# Script-only runtime follow-ups

These changes implement the script-only tickets recorded under
`.scratch/runtime-hardening/issues/`. They do not change Worker/Planner skills,
FIX/test permissions, bounded research completion policy, or introduce verification
resume. Existing daemons load these changes only after an operator restart.

## Retained attempts

Before attempt recovery or legacy rollback clears the project, the failure archive
gets an `attempt/` package. Explicit clean-start packages live in the selected
lifecycle directory under `retained/<identity>/`. A package includes HEAD history
as a Git bundle, separate staged/worktree binary diffs, untracked contents,
symlinks, file modes, checksums and task/attempt context where available.
Ignored files are excluded. Packages have a private directory; they can contain
the same sensitive contents as tracked and nonignored project files.

Before cleanup, a temporary checkout independently reconstructs HEAD, index and
files. Capture, checksum, restoration or concurrent-source-change failure refuses
cleanup. Partial packages stay available for diagnosis. Recheck a saved package:

```sh
python3 scripts/attempt_archive.py /path/to/archive/attempt
```

This is evidence retention, not permission to continue a rejected implementation.
The existing baseline recovery and explicit clean restart semantics still apply.
No automatic retention pruning is added: the existing scratch review protects
unresolved/referenced failed attempts; standalone `retained/` packages require
explicit operator housekeeping. Do not delete a package referenced by diagnosis.

## Readiness before queue claim

The daemon checks product-directory access and a create/read/remove roundtrip in
its lifecycle scratch before claiming queued work. A registration may additionally
configure `worker.preflight`:

```json
{
  "required_tools": ["git", "python3"],
  "timeout": 15,
  "argv": ["{executable}", "sandbox", "-P", "my-worker-profile",
           "/usr/bin/python3", "{probe}", "{project}", "{state}"]
}
```

This example is for a Codex registration whose actual Worker uses that named
profile. Choose argv from the installed executable's help and match the effective
sandbox/profile and project/runner access used by the Worker. No model command is
launched by preflight. `{executable}`, `{probe}`, `{project}` and `{state}` replace
whole argv elements only; other arguments are literal. The registration's env is
inherited by the probe. Probe commands are trusted configured project code.

Without explicit argv, readiness establishes host access only, not adapter sandbox
readiness. `sandbox_probes` reports the number actually executed. Never configure
a probe that changes product files or security policy. The bundled probe writes
only its own temporary runner files. Include a parser smoke command in your
configured probe if that deployment requires the code-index environment.

Failure records command, registration, exit, bounded combined output and timeout
under `lifecycle/preflight.json`, exposes `ENVIRONMENT_BLOCKED`, leaves queue order
and score feedback intact, and deduplicates unchanged failure notifications.
Normal polling retries prerequisites; `RUN_ONCE` exits 2 on a blocked environment.
This adds no automatic package installation or security-policy changes.

## Live verification evidence

On POSIX, VERIFY writes combined output as it arrives to
`lifecycle/verify/<identity>.log`. Its sibling JSON names PID, command, start time,
budget, elapsed time, output bytes and exit/timeout. The in-memory return keeps
at most 64 KiB; the log retains full output. Gate evidence includes `log_path`;
structured verification failures include `verify_log_path`.

For an ad-hoc command without a selected runner, a read-only Git state directory
uses workspace `.scratch/nightshift-verify/` instead. An explicitly selected
runner that cannot store logs fails visibly rather than redirecting evidence.

The shared phase deadline still applies. Timeout sends TERM to the owned process
group, waits two seconds, then KILL and bounded reap/drain. A child that explicitly
detaches into another session is outside that group. A daemon heartbeat is not a
case-progress signal, and these observations do not assert an engine stall cause.
Windows keeps the previous VERIFY implementation; this change adds no new native
Windows live-log guarantee. Historical logs require operator retention management.

## Evidence capability declarations

The project's acceptance config may include:

```json
"capabilities": {
  "frameworks": [
    {"name":"unittest", "id_prefixes":["test_"]},
    {"name":"gut", "id_prefixes":["tests/"]}
  ],
  "case_selection": false
}
```

These are declared ID namespaces, not framework auto-detection or executable
discovery. Adapter evidence must agree with the manifest. Unsupported namespaces
receive a distinct handoff error; unknown IDs within a supported namespace still
fail. Existing nonce, source mapping, fingerprints, permanent discovery and actual
outcome checks remain mandatory. Omit the optional manifest for legacy adapters.
Actual Python/GUT discovery and execution remain product-owned.

## Opt-in durable hooks

Set `acceptance.durable_hooks` to `true` to save hook state atomically under
`lifecycle/hook-state.json`. Default remains session-only. Persistence binds state
to the resolved project and periodic-hook definitions; incompatible state is
retained and startup fails explicitly for review. One-shot registrations, pending
runs, counters, accepted event identities and passed/cancelled run markers survive
relaunch. Revision/clean-tree guards remain in force.

A run persisted as `running` becomes `interrupted` after relaunch. Dispatch waits
in `HOOK_INTERRUPTED` until an operator inspects possible side effects and makes
an explicit choice; execution is never automatically assumed safe to repeat.
Exactly-once external side effects cannot be promised across a crash.

```sh
python3 scripts/worker_runtime.py hook-list --root . --config /path/to/config.json
python3 scripts/worker_runtime.py hook-cancel --root . --config /path/to/config.json --run-id ID
python3 scripts/worker_runtime.py hook-retry --root . --config /path/to/config.json --run-id ID
```

These commands use the live daemon's existing control channel. To cancel an
unfired one-shot registration, pass its hook ID; for a scheduled run, pass its run
ID. Retrying a failed hook under a failure pause still requires the existing
explicit `restart` command. Commands should use `NIGHTSHIFT_HOOK_RUN_ID` to deduplicate
effects. Hook state is not loaded when durability is disabled. Changing config or
disabling persistence does not automatically discard the retained ledger.
`hook-list` returns up to 20 summaries at a time; use `--offset 20`, `--offset 40`,
and so on to inspect further runs/registrations without exceeding pipe bounds.

## Capacity inspection

`score-read` now includes a bounded recent feedback window, outcome counts and
accept streak. Counts distinguish hard failures from accept/reject/no-fault;
they are event counts, not a calibrated success probability. Score arithmetic and
event idempotency are unchanged.

```sh
python3 scripts/worker_runtime.py capacity --root . --config /path/to/config.json
```

`capacity` reads per-registration scores and the latest readiness result without
creating missing score/state files. Missing history is `unknown`. This view does
not infer causes for older failures or increase action budgets. It also reads up
to 20 recent task/failure records, including recorded level, target entry count,
actions, elapsed time and failure phase/kind. Missing fields remain unknown;
target entries are not a measurement of lines changed. Richer task-size policy
and post-execution failure attribution remain future work.

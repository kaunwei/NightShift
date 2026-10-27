# NightShift deployment guide

## Ownership and layout

Install NightShift into an existing project with `./install.sh /path/to/project`. The installer uses `nightshift/install-manifest.json` to deploy runtime files and tools under the project's `nightshift/` directory; configuration and Worker state are initialized only when missing. Development docs and experiments stay in the NightShift source checkout. Skills use the root discovery paths in both source and consuming projects. The agent host's discovery entries remain under `.agents/skills/` and `.skills/` so Planner and Worker skills are loaded by the host.

Key paths in an installed project:

- `nightshift/worker.sh`, `nightshift/worker_runtime.py`: Worker entry point and runtime.
- `nightshift/adapters/`: protocol adapters and the project-owned `agents.json` registry.
- `nightshift/tools/`: multi-language Tree-sitter indexer, parser registry, requirements, and private `.venv`.
- `nightshift/code-index.toml`: project-owned source selection and `tool`/`project` scope rules.
- `nightshift/tasks.txt`, `nightshift/tasks.done`, `nightshift/progress.log`, `nightshift/worker.status`, `nightshift/.worker.log`, and `nightshift/.worker.notes.md`: queue, history, runtime evidence, status, logs, and reusable environment notes.
- `nightshift/.worker-*`: score, event, ghost, and related runtime state.
- `nightshift/.scratch/`: attempt baselines and failed-task recovery snapshots.
- `.reports/`, `.trials/`, and application source folders remain in the project root because they describe or contain project work.

## Install and update

Run the same installer for a fresh install or update:

```sh
./install.sh /path/to/project
```

The installed copy is `nightshift/install.sh`; running it again from the target updates that installation. There is no separate updater. The installer refreshes NightShift files, preserves the project-owned index config and agent registry, migrates old root-level Worker state into `nightshift/`, and installs `tree-sitter-language-pack` with pip into `nightshift/tools/.venv`. It validates shell and Python syntax before reporting success.

Older NightShift files can be removed with the temporary `./remove.sh /path/to/project` helper. It removes the NightShift package, old root-level runtime/state files, and the NightShift skill namespace while retaining application code, unrelated scripts/docs/skills, and the project-owned code-index scope config. It leaves `.worker-tree`, `.preview`, and `.trials` intact because they can hold unfinished or delivered work.

## Agent configuration

Edit `nightshift/adapters/agents.json`. Each named entry separates Worker limits from the selected adapter and executable:

```json
{
  "codex-main": {
    "default": true,
    "worker": { "task_timeout_seconds": 1800 },
    "agent": {
      "adapter": "codex",
      "command": "codex",
      "args": [],
      "env": {},
      "config": { "model": "gpt-6.1-sol", "effort": "low" }
    }
  }
}
```

Skills install only to `.agents/skills/nightshift/`, shared `.agents/skills/<category>/<skill>/` packages and `.skills/universal-build-verify.md`, including their referenced resources. Updates remove exact retired NightShift assets while preserving unknown project notes.

The installer preserves an existing registry and migrates a legacy `agents/agents.json` or `scripts/adapters/agents.json`. A registration returning no response or a confirmed timeout may fail over in registry order; the runtime records a Planner review gate before replacement work proceeds.

## Run, pause, and inspect

From the project root:

```sh
./nightshift/worker.sh
RUN_ONCE=1 ./nightshift/worker.sh
./nightshift/status.sh
./nightshift/reorder_queue.sh prepared-queue.txt
```

The queue is `nightshift/tasks.txt`. Create `nightshift/PAUSE` to stop future claims after the active task finishes, then remove that file to resume. Check `nightshift/worker.status` to confirm the Worker is paused and has no active task. `nightshift/watch_worker.sh` can watch a task and process durable agent events.

Worker execution stays in the project root so task targets and Git operations refer to application files. Runtime state paths are absolute paths under `nightshift/` by default; explicit environment overrides remain supported. Application reports and staged trials remain under `.reports/` and `.trials/`.

## Scratch review

Worker checks scratch pressure at startup, task boundaries and every 60 idle seconds. Defaults:
`SCRATCH_REVIEW_ATTEMPTS_MB=100`, `SCRATCH_REVIEW_FAILED_MB=100`,
`SCRATCH_REVIEW_FAILED_DIRS=20`; zero disables an individual trigger and
`SCRATCH_REVIEW_ENABLED=0` disables monitoring. Values are inherited environment settings.
The monitor reads file metadata only and inserts one deduplicated `SCRATCH-REVIEW-*` ticket.
After review, unchanged pressure waits 24 hours; growth of at least 25% (minimum 1 MiB or 5 failure directories)
allows another review sooner. Queued/active reviews are retained; an orphaned claim is requeued after 120 seconds.

The ticket asks Worker to inspect at most eight candidates and remove at most five whole directories:
only artifacts older than seven days, matching their task/attempt identity, with accepted final work and
no live references. Recovery archives also need successful recovery proof. Newest per-task diagnostic
anchors, active/pending/retried/unresolved work, unknown evidence, symlinks and the code index stay.
Internal maintenance attempts use the runtime's completion receipt instead of Planner acceptance.
These are Worker prompt rules, not a filesystem deletion sandbox; the monitor never deletes artifacts.

Worker overwrites `nightshift/.scratch/review/last-review.json` (maximum 1,024 bytes) with byte counts,
removed paths, kept counts and a short note. The fixed scheduler state and lock are in the same directory.
No report history, normal task audit/score entry or Planner skill change is added. A failed review produces
a compact failure report and normal queued work continues; cancellation, provider gates and unsafe recovery
retain the existing runtime stop/retry behavior.

Read only current sizes without creating a ticket:
`python3 nightshift/worker_runtime.py scratch-review-check --root . --stats-only`.

## Code index

The installer creates the parser environment automatically. Agents use `nightshift/.scratch/code-index/INDEX.md` (at most 8 KiB); `index.json` in the same directory is script-owned cache. Build and query from the consuming repository root:

```sh
python3 nightshift/worker_runtime.py code-index build
python3 nightshift/worker_runtime.py code-index query symbol ExampleType --scope project --format compact
```

Use `--scope project` for application code, `--scope tool` for `nightshift/tools/`, or `--scope all` when a change crosses both. The index reports Tree-sitter syntax evidence; reference and caller matches are leads, not compiler-resolved bindings.

## Verification

The source repository tests use fake agents and do not call a live model:

```sh
python3 -m unittest discover -s test -v
bash -n install.sh remove.sh nightshift/*.sh
```

The install smoke test removes a disposable install, installs it again, checks parser dependencies, then runs code and research tickets through the installed Worker.

# Install NightShift in another repository

## External adapter protocol (version 1)

A registered adapter is an executable command plus optional fixed arguments. The runtime invokes it as `COMMAND [ARGS...] CALLBACK`, writes exactly one JSON request to stdin, and reads exactly one JSON response from stdout. Send diagnostics to stderr; stdout must not contain banners or log lines. Every request and response uses `protocol_version: 1`. Unsupported versions and malformed responses fail before task execution.

The callbacks are:

| Callback | Required request fields | Required response fields |
|---|---|---|
| `get_config` | `protocol_version`, `registration_id`, `overrides` | `protocol_version`, `initial_score` (integer 1–5), optional `limits`, `configuration` |
| `start` | `protocol_version`, `task_id`, `task_version`, `attempt_id`, `working_directory`, `prompt_path`, `output_dir`, `result_path`, `configuration`, `limits`, `environment` | `execution_id`, `status_location` |
| `status` | `protocol_version`, `execution_id`, `status_location` | `status`: `running`, `complete`, `closeout_required`, `quota_exhausted`, `step_budget_exceeded`, `failed`, or `cancelled`; terminal results may include `result_location` |
| `closeout` | `protocol_version`, `execution_id`, `prompt_path`, `output_dir`, `result_path`, remaining budget and deadline | `execution_id`, `status_location` |
| `cancel` | `protocol_version`, `execution_id`, reason and stop deadline | a termination result |

Register the executable without adding its name to NightShift:

```json
[
  {"id":"team-model-a", "adapter":"team-adapter", "command":"/opt/team/adapter", "args":[], "env":{}, "model":"model-a", "overrides":{"region":"west"}}
]
```

`adapter` is an opaque registration label. `command` and `args` select the executable; `env` adds string environment entries; `model`, `effort`, and arbitrary JSON `overrides` are passed to `get_config` for adapter-owned interpretation. Multiple registrations may name the same adapter executable with different IDs and overrides.

`start` and `closeout` must return promptly with an execution handle; they do not wait for model work to finish. `status` reads local state and must not call a model or query quota. The adapter interprets registration overrides and returns normalized settings under `configuration`. `limits.poll_interval_seconds` and `limits.callback_timeout_seconds` are seconds; callback timeout limits each individual callback response, while the task execution timeout independently limits the full work after `start`. A responsive `running` status never extends the task deadline. On timeout, `cancel` must stop the execution and return `stopped: true`; an accepted request without confirmed termination is a cancellation failure. The runtime kills timed-out callback process groups, then requests cancellation of the managed execution. A completed execution points to a JSON result file; result fields are task outcome, evidence, change/no-change information, and `commit_message`. Do not write protocol data to stderr or diagnostics to stdout. The runtime keeps callback stdout and stderr separate.

The runtime may issue at most one private `closeout` per original task ID, including retries, agent switching, and process restart. The request keeps the original registration, task version, attempt context, and execution ID, but has a distinct prompt, output directory, and result file. Closeout receives remaining action and time limits. It may verify and provide the missing structured result or commit message; it must not edit implementation files or commit. The runtime persists the allowance and internal artifacts under `.worker-ghost-state*.json` and `.worker-ghosts/`. Closeout failure is reported as the original task result and does not select a replacement adapter. A valid `no_change` result skips closeout.

Before an execution attempt, the runtime snapshots the current commit, index, tracked dirty files, and untracked workspace files. If an attempt fails and the old execution has stopped, it archives its diff, status, commits, and changed files under `.scratch/failed_tasks/`, then restores the captured state before another registration starts. The archive is unique per attempt. If the baseline is missing, the reset fails, or exact restoration cannot be confirmed, the task is requeued and dispatch stops; the next adapter is not started. Runtime queue, score, agent, ghost, and progress state remains current across restoration.

## Per-registration capability scores

For protocol adapters, the first successful `get_config` initializes a score file for that registration from `initial_score` (1–5). Registration IDs are the score identity: two model profiles using one executable keep separate score, acceptance window, and failure history. No score is inferred from the adapter name. Feedback uses the existing arithmetic and can target a registration directly:

```sh
python3 scripts/worker_runtime.py score-read --state .worker-agent-scores --agent-id model-a
python3 scripts/worker_runtime.py score-record --state .worker-agent-scores --agent-id model-a \
  --task-id TASK-123 --result accept --events .worker-agent-events.jsonl
```

Add `--mid-batch` when a score change occurs before the next batch boundary; the durable event records cause, task, registration, previous/current score, and previous/current task level. Normal feedback records a batch-boundary cause. Ghost execution does not initialize or update its own score. Existing `.worker-score.json` remains intact for inspection; NightShift does not guess which registration owns its historical shared score. New score files live under `.worker-agent-scores/`.

## Planner handoff for capability changes

Every registration score change creates a durable event and raises `.worker-dispatch-gate.json`. `watch_worker.sh` runs the event watcher and appends one `[PLANNER_REVIEW_REQUIRED]` handoff to `progress.log` for each event, including after a watcher restart. The sentinel does not invoke Planner or rewrite queued work. New task dispatch stays paused until the Planner has reviewed the affected work and an operator records a resolution:

```sh
python3 scripts/worker_runtime.py agent-event-ack --events .worker-agent-events.jsonl \
  --acknowledgements .worker-agent-events.acks.jsonl --event-id EVENT_ID --resolution revised
```

Use `acknowledged` when the queued work remains valid, or `revised` after updating it. The next watcher pass clears the gate when every event is resolved; already-running work may finish. `AGENT_DISPATCH_GATE_FILE`, `WORKER_AGENT_EVENTS_FILE`, `WORKER_AGENT_EVENTS_CURSOR_FILE`, and `WORKER_AGENT_EVENTS_ACK_FILE` can override the default artifact paths.

The runtime implements configuration discovery, asynchronous `start`, local `status`, cancellation, and private closeout for arbitrary adapter names. Configure migrated built-in providers through the adapter registry when using this lifecycle.

## Migrating a generic executable wrapper

Set the profile adapter to `generic` and the command to Python with the shipped compatibility adapter as its argument. Pass the previous wrapper executable and fixed arguments through overrides:

```json
[{"id":"custom","adapter":"generic","command":"python3",
  "args":["scripts/adapters/generic.py"],
  "overrides":{"executable":"./my-worker","args":["--quiet"],
    "model":"model-name","effort":"high","env":{"MY_SETTING":"value"}}}]
```

The wrapper receives `NIGHTSHIFT_PROMPT_FILE`, `NIGHTSHIFT_RESULT_FILE`, `NIGHTSHIFT_TASK_ID`, `NIGHTSHIFT_EXECUTION_KIND` (`main` or `closeout`), `NIGHTSHIFT_MODEL`, `NIGHTSHIFT_EFFORT`, `NIGHTSHIFT_ACTION_LIMIT`, `NIGHTSHIFT_EXECUTION_TIMEOUT`, `PORT`, and `TEST_PORT`. It must write one JSON object to the result path with a supported `outcome`; successful outcomes also require the standard evidence, change, and `commit_message` fields. The wrapper owns enforcement of action limits and duration using the supplied values. Text-only legacy wrappers fail with an actionable structured-result diagnostic; migrate them to write protocol JSON before switching registrations.

## Legacy configuration migration

Replace `AI_CLI`, `AI_MODEL`, `AI_EFFORT`, provider-based `AI_AGENTS_JSON`, and native `CODEX_*`/`AGY_MODE` routing with explicit adapter registrations. The Codex and AgY adapters accept their executable and model settings under `overrides`; generic wrappers use the compatibility adapter above. Keep the same profile IDs when possible so per-registration score history remains associated with the same capability. The legacy shared `.worker-score.json` is retained for inspection and is not assigned to a registration automatically. The installer deploys the adapter scripts and this guide while preserving an existing `.worker.env`; migrate that file deliberately after reviewing the example.

NightShift can be deployed into an existing repository with `install.sh`. The script requires the target directory to exist and refuses to install into the NightShift source repository itself.

```sh
./install.sh /path/to/target-project
```

`update.sh` is an alias for the same installer behavior:

```sh
./update.sh /path/to/target-project
```

## What installation changes

The installer copies or updates NightShift-owned files: `worker.sh`, `scripts/`, the runtime regression tests under `test/nightshift_worker/`, `.worker.env.example`, `.skills/universal-build-verify.md`, and the shipped `.agents/skills/` categories. It initializes missing queue, history, notes, and granularity files; existing `.agents/skills.json`, `.worker.env`, queue, history, notes, and granularity profile are preserved. It adds missing NightShift ignore entries to `.gitignore` and validates Bash and Python syntax.

An update overwrites the deployed NightShift-owned runtime, helper, test, example, and skill files. It also removes a fixed list of legacy NightShift skill directories. Review the target repository's working tree before updating if those paths contain local edits. The installer does not edit the target's application code, `AGENTS.md`, `CLAUDE.md`, or `README.md`.

## Configure and run

On a fresh installation, `.worker.env` is initialized from `.worker.env.example`. On an existing installation, the current `.worker.env` is left intact; compare it with the updated example when new settings are introduced.

The example selects Codex with `gpt-6-luna` and `none` effort. `AI_AGENTS_JSON` optionally configures ordered CLI profiles. Failover happens only after a failed CLI call reports a recognized quota or rate-limit error. When all configured profiles are exhausted, the runtime requeues the current ticket and waits for the exhausted-agent state to be reset; it does not query quota in advance. Explicit `RUN_ONCE=1` tests exit instead.

Use `/planner` for ticket planning and acceptance, `/explore` for read-only seam research, and `./worker.sh` to run the queue. The runtime handles one ticket at a time. It does not start a Planner agent or automatically integrate the Worker branch into the main checkout. See the [complete behavior specification](NIGHTSHIFT_SPEC.md) before relying on any workflow detail.

## Verify the deployment

From the target repository:

```sh
bash -n worker.sh scripts/*.sh
python3 -m unittest discover -s test -v
RUN_ONCE=1 ./worker.sh
./scripts/status.sh
```

The test suite uses a fake CLI and does not call a live model. The empty-queue run checks startup and exits when no task is queued. Inspect `worker.status` and `progress.log` for runtime state and outcomes; a mechanical audit PASS still requires Planner acceptance.

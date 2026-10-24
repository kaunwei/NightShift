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

Register the executable in the shared name-keyed registry without adding its name to NightShift:

```json
{
  "team-model-a": {
    "default": true,
    "adapter": "team-adapter",
    "command": "/opt/team/adapter",
    "args": [],
    "env": {},
    "config": {"model": "model-a", "region": "west"}
  }
}
```

The object key is the stable registration ID. `adapter` is opaque; `command` and `args` select the executable, and `env` adds string environment entries. The `config` object, including model/effort and tool settings, is passed as callback `overrides` to `get_config` for adapter interpretation. Callback `overrides` is a protocol field, not another registry format. Default registrations run first; JSON order is retained within each priority group. Multiple names may use one executable with different config.

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

Set `agent.adapter` to `generic` and `agent.command` to the real wrapper executable. Put fixed wrapper arguments and environment in `agent.args` and `agent.env`:

```json
{"custom":{"default":true,"worker":{"task_timeout_seconds":1800},
  "agent":{"adapter":"generic","command":"./my-worker","args":["--quiet"],
    "env":{"MY_SETTING":"value"},"config":{"model":"model-name","effort":"high"}}}}
```

The wrapper receives `NIGHTSHIFT_PROMPT_FILE`, `NIGHTSHIFT_RESULT_FILE`, `NIGHTSHIFT_TASK_ID`, `NIGHTSHIFT_EXECUTION_KIND` (`main` or `closeout`), `NIGHTSHIFT_MODEL`, `NIGHTSHIFT_EFFORT`, `NIGHTSHIFT_ACTION_LIMIT`, `NIGHTSHIFT_EXECUTION_TIMEOUT`, `PORT`, and `TEST_PORT`. It must write one JSON object to the result path with a supported `outcome`; successful outcomes also require the standard evidence, change, and `commit_message` fields. The wrapper owns enforcement of action limits and duration using the supplied values. Text-only legacy wrappers fail with an actionable structured-result diagnostic; migrate them to write protocol JSON before switching registrations.

## Legacy configuration migration

Put worker-wide runtime settings in `worker.sh`. Put agent registrations in the single `scripts/adapters/agents.json` object, keyed by stable agent name. Each entry has `default`, a `worker` object for Worker limits such as `task_timeout_seconds`, and an `agent` object for adapter name, real executable command, optional arguments/environment, and provider-specific `config`. The Worker launches the selected Python protocol adapter internally; `agent.command` names the executable that adapter runs (for example `codex`, `agy`, or a generic wrapper), never the Python adapter launcher. The Worker orders entries with `default: true` first and retains JSON order for the rest. Codex and AgY settings belong in each `agent.config`; generic wrapper settings use the compatibility adapter above. Keep agent names stable so per-agent score history remains associated with the same capability. The legacy shared `.worker-score.json` is retained for inspection and is not assigned to an agent automatically. The installer deploys the adapter scripts and initializes `scripts/adapters/agents.json` only when it is missing; updates preserve the project's registry and migrate an existing `agents/agents.json` in place.

NightShift can be deployed into an existing repository with `install.sh`. The script requires the target directory to exist and refuses to install into the NightShift source repository itself.

```sh
./install.sh /path/to/target-project
```

`update.sh` is an alias for the same installer behavior:

```sh
./update.sh /path/to/target-project
```

## What installation changes

The installer copies or updates NightShift-owned files: `worker.sh`, `update.sh`, `scripts/`, `scripts/adapters/agents.json` when absent, the runtime regression tests under `test/nightshift_worker/`, `.skills/universal-build-verify.md`, and the shipped `.agents/skills/` categories. The deployed `update.sh` can update the same project again. It initializes missing queue, history, notes, and granularity files; existing `.agents/skills.json`, agent registry, queue, history, notes, and granularity profile are preserved. It adds missing NightShift ignore entries to `.gitignore` and validates Bash and Python syntax.

An update overwrites the deployed NightShift-owned runtime, helper, test, example, and skill files. It also removes a fixed list of legacy NightShift skill directories. Review the target repository's working tree before updating if those paths contain local edits. The installer does not edit the target's application code, `AGENTS.md`, `CLAUDE.md`, or `README.md`.

## Upgrading from isolated Worker deployments

The Worker now runs tasks in the target project directory. `.worker.env` is no longer read by the launcher, runtime, or helper scripts; move operational settings into `worker.sh` and agent settings into `scripts/adapters/agents.json`. Updates migrate the old `agents/agents.json` to the new location while preserving its contents. Updates remove the obsolete `.worker.env.example`, but leave an existing `.worker.env` untouched so local values can be migrated without losing data. The installer does not delete `.worker-tree`, its branches, or `.preview`; those locations may contain unintegrated work. Before removing any of them yourself, inspect the worktree status and commits, compare its branch with the project branch, and review preview artifacts. Unmerged work is not copied into the project directory automatically. The status dashboard no longer reports preview versions. New verified trial task outputs belong under `.trials/<TASK-ID>/`, which the installer ignores so binary-only deliveries do not become source commits. Build and verify the staged copy before publishing its directory; remove only the current task ID’s incomplete output when a check fails. A trial that needs a shared project resource should include the exact dependency and conflict in its handoff. Resolve the deployed `PAUSE_FILE` before recommending a pause; relative values are rooted at the installation directory, and `./scripts/status.sh` confirms whether the user-created flag has reached the PAUSED state. The flag stops future claims after the active task completes; it does not cancel that task.

## Runtime settings and helper commands

There is no worker env configuration file to create or source. Runtime defaults are at the top of the launcher and can be overridden by the launch environment. Agent models, effort, permissions and tool-specific values belong in the shared registry's config objects. Updates replace the owned launcher; review and reapply local default edits, or maintain the values as launch-environment overrides. Updates preserve an existing registry and keep legacy env data only for manual migration.

Helpers use their own defaults and environment overrides; they do not source the launcher. For a custom pause/status/queue path or Worker ID, pass the same resolved settings to the helper. Planner obtains these values from the actual Worker launch configuration, not the removed env file. Relative runtime paths are rooted at the project directory; preserve absolute paths. Provide concrete pause-flag creation and matching status commands for that deployment. A pause flag holds future claims after the active task completes; wait for PAUSED with no current task before trying conflicting resources. A trial task never sets the flag itself.

## Configure and run

On a fresh installation, `worker.sh` supplies worker runtime defaults and `scripts/adapters/agents.json` supplies the default Codex and backup AgY registrations. Configure at least one named agent before adding work to the queue. Each entry sets its Worker timeout under `worker.task_timeout_seconds`, then selects an adapter and real executable command under `agent`; provider options go in `agent.config`. `default: true` makes it a first candidate. Failover follows the remaining JSON order after quota exhaustion or a confirmed timeout. The runtime restores the failed attempt and raises a durable Planner gate before a replacement starts. After Planner review, use the `agent-event-ack` CLI shown above with resolution `acknowledged` or `revised`, then let the watcher resolve the gate. When all registrations are quota-exhausted, the task remains queued until the exhausted state is reset; explicit `RUN_ONCE=1` exits instead of waiting.

Use `/planner` for ticket planning and acceptance, `/explore` for read-only seam research, and `./worker.sh` to run the queue. The runtime handles one ticket at a time. It runs directly in the project directory and does not start a Planner agent or maintain an isolated Worker branch. See the [complete behavior specification](NIGHTSHIFT_SPEC.md) before relying on any workflow detail.

## Verify the deployment

From the target repository:

```sh
bash -n worker.sh scripts/*.sh
python3 -m unittest discover -s test -v
RUN_ONCE=1 ./worker.sh
./scripts/status.sh
```

The test suite uses a fake CLI and does not call a live model. The empty-queue run checks startup and exits when no task is queued. Inspect `worker.status` and `progress.log` for runtime state and outcomes; a mechanical audit PASS still requires Planner acceptance.

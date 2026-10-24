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

The runtime currently implements configuration discovery, asynchronous `start`, and local `status` for arbitrary adapter names. Cancellation and closeout are wired into the subsequent lifecycle migration tickets. Until those tickets are complete, configure migrated built-in providers on their existing paths.

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

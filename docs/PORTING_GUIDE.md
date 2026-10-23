# Install NightShift in another repository

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

The example selects Codex with `gpt-6-luna` and `none` effort. `AI_AGENTS_JSON` optionally configures ordered CLI profiles. Failover happens only after a failed CLI call reports a recognized quota or rate-limit error. When all configured profiles are exhausted, the runtime requeues the current ticket and stops; it does not query quota in advance.

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

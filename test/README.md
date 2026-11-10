# Worker regression tests

From the repository root, run `scripts/tools/setup.sh` once to install the parser dependencies, then:

```sh
NIGHTSHIFT_TEST_PARSER_VENV="$PWD/scripts/tools/.venv" \
  scripts/tools/.venv/bin/python -m unittest discover -s test -v
```

An existing compatible parser environment can be supplied instead. Installer fixtures reuse it,
so the test run needs no package downloads. Worker tests use fake executables; no model calls or tokens are consumed.

Standalone daemon fixtures should use `runtime_fixture.deploy_runtime` to copy
the files declared by the deployment manifest. Partial module lists can fail at
startup before a test reaches its intended assertion. Use the production ignore
rules for generated runtime files, and explicitly set a fixture registration's
initial score when its tickets require L1 capability.

The former six-failure baseline was repaired rather than allowlisted: five
daemon tests had incomplete deployments; the two scratch-review fixtures also
had a mismatched initial score and omitted Python cache ignores. The launcher
test's obsolete forced-persistent expectation was replaced by separate explicit
persistent-retry and RUN_ONCE exit-status checks. The functional coverage remains.

Keep new tests at public seams: the `scripts/worker_runtime.py` commands, the
`scripts/worker.sh` launcher, and the `scripts/status.sh` dashboard. For each behavior change, add a
failing test with a fixed expected result, make the smallest implementation
change, then run the whole suite. Coverage includes task claiming, Codex/agy
CLI invocation, Luna/none settings, wrapper commits, mechanical and Git audit
gates, report artifacts, rollback, polling states and budgets, timeout
exit-code/process-termination behavior, shared-score transitions, and restricted
Codex/AgY ghost closeout auditing.

`test/fixtures/trial-demo/` is installed into a temporary project by the trial demo integration test. It covers a standalone binary, a script with a bundled resource, a project-shared file, `.trials/` ignore behavior, and a custom `PAUSE_FILE`, and that trial delivery does not pause the Worker; no live model is used.

`python3 -m unittest test.test_scratch_review` checks threshold/deduplication, orphan recovery, cooldown, bounded reports, symlink refusal and real-daemon maintenance success/failure followed by normal work (fake agent, no model calls).

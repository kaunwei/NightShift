# Worker regression tests

From the repository root, run `nightshift/tools/setup.sh` once to install the parser dependencies, then:

```sh
NIGHTSHIFT_TEST_PARSER_VENV="$PWD/nightshift/tools/.venv" \
  nightshift/tools/.venv/bin/python -m unittest discover -s test -v
```

An existing compatible parser environment can be supplied instead. Installer fixtures reuse it,
so the test run needs no package downloads. Worker tests use fake executables; no model calls or tokens are consumed.

Keep new tests at public seams: the `nightshift/worker_runtime.py` commands, the
`nightshift/worker.sh` launcher, and the `nightshift/status.sh` dashboard. For each behavior change, add a
failing test with a fixed expected result, make the smallest implementation
change, then run the whole suite. Coverage includes task claiming, Codex/agy
CLI invocation, Luna/none settings, wrapper commits, mechanical and Git audit
gates, report artifacts, rollback, polling states and budgets, timeout
exit-code/process-termination behavior, shared-score transitions, and restricted
Codex/AgY ghost closeout auditing.

`test/fixtures/trial-demo/` is installed into a temporary project by the trial demo integration test. It covers a standalone binary, a script with a bundled resource, a project-shared file, `.trials/` ignore behavior, and a custom `PAUSE_FILE`, and that trial delivery does not pause the Worker; no live model is used.

`python3 -m unittest test.test_scratch_review` checks threshold/deduplication, orphan recovery, cooldown, bounded reports, symlink refusal and real-daemon maintenance success/failure followed by normal work (fake agent, no model calls).

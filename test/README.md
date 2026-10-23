# Worker regression tests

Run `python3 -m unittest discover -s test -v` from the repository root. The suite
uses only Python's standard library and a fake `codex` executable; it never
contacts a model or consumes tokens.

Keep new tests at public seams: the `scripts/worker_runtime.py` commands, the
`worker.sh` launcher, and the status dashboard. For each behavior change, add a
failing test with a fixed expected result, make the smallest implementation
change, then run the whole suite. Coverage includes task claiming, Codex/agy
CLI invocation, Luna/none settings, wrapper commits, mechanical and Git audit
gates, report artifacts, rollback, polling states and budgets, and timeout
exit-code/process-termination behavior.

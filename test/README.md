# Worker regression tests

Run `python3 -m unittest discover -s test -v` from the repository root. The suite
uses only Python's standard library and a fake `codex` executable; it never
contacts a model or consumes tokens.

Keep new tests at public seams: the `worker_runtime.py` commands and the
`worker.sh` entry point. For each behavior change, add a failing test with a
fixed expected result, make the smallest implementation change, then run the
whole suite. The integration fixture covers task claiming, Luna/none CLI
arguments, wrapper commit, status, Git audit acceptance and rejection, rollback,
and timeout exit-code/process-termination behavior.

The staged migration leaves task execution, agy, isolation, and preview logic
in Bash for now. Move one verified behavior at a
time; do not remove an old path until its external contract is covered here.

# NightShift

Vocabulary for unattended execution and Planner supervision.

## Language

**NightShift**: The unattended dual-terminal AI development framework.
_Avoid_: auto_script, script_repo

**Automatic acceptance**: Runtime approval after hot, TDD evidence and mechanical
checks pass, followed by commit and automatic scoring.
_Avoid_: Planner acceptance, automatic merge

**Hot**: The project's precommit test gate, including persistent TDD coverage and
task-required checks.

**Cold**: An independent periodic regression task whose failure creates a new issue.

**Ghost**: A bounded assistant for handoff metadata, existing-test wiring and diagnosis.

**Planner recovery**: Replanning ordinary issue tasks and explicitly restarting
execution after an unresolved failure. Each new Worker starts clean.
_Avoid_: continuing failed work, automatic resume

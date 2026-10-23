# Skill and prompt equivalence review

Compared with the pre-edit versions at `e3e65cb`. This is an instruction-preserving edit; runtime algorithms and CLI behavior are unchanged.

| Original requirement | Current source |
| --- | --- |
| Domain/ADR maintenance, public seams, full-horizon queue, alignment/auto mode | Planner workflow + OPERATIONS.md slicing |
| Shared score, initial 5, level ladder, five accepts, hard failures, human model control | Planner score section + OPERATIONS.md blueprints |
| Track A/B file/score thresholds, structural closure, four refactor gates | OPERATIONS.md slicing |
| Every-10 review, architecture inspection, refactor queue | OPERATIONS.md slicing |
| Queue Sentinel, mechanical audit, fast-track merge, deep review, report archive | OPERATIONS.md acceptance |
| Guidance/decomposition/blocked feedback, Clean Pivot, intervention exceptions | OPERATIONS.md recovery |
| Isolated/in-place execution, preview/drop-box, steering, requested env updates | OPERATIONS.md preview |
| Report freshness, explicit exploration, compiler probes, 5 KB limit, skeleton attachment, exact digest fields | Explore |
| Target whitelist, immutable tests, assertion count, deletion ceilings, warnings/lint, archetypes | Worker execution contract |
| Three attempts, evidence/negative proof, confidence, notes, commits/progress ownership | Worker execution contract |
| Step formula/reserve, AgY markers, Codex events, per-call timeout, ghost handoff and original-task attribution | Runtime prompt + Worker contract + Planner score section |

Corrections made during review: restored requirements that had become optional, fixed relative skill links, replaced obsolete subagent JSON with the same Sentinel role through the available interface, and routed failed-task cleanup through the existing runtime's preserved rollback. Clean Pivot retains its recovery purpose and session-base operation within authorized scope. Command-format examples were removed while retaining structural verification and step accounting.

Verification: full standard-library regression suite (51 tests), local Markdown targets, Python/shell syntax, diff whitespace, and installer deployment of the disclosed operations reference. These checks verify static instructions and runtime contracts; they do not measure model compliance in a live task.

# Domain Glossary

This file defines the canonical vocabulary for the project. When discussing or implementing features, stick to these terms.

## Terms

| Term | Definition | Avoid |
| :--- | :--------- | :---- |
| **NightShift** | The 24-hour unattended dual-terminal AI development framework. | auto_script, script_repo, scripts |

## Acceptance lifecycle

**Planner acceptance rollback**:
The Planner-controlled rejection of candidate commits and restoration of the last accepted commit before work is replanned.
_Avoid_: Planner cancellation, task completion

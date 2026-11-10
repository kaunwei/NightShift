"""Evidence-backed automatic score attribution; unknown causes stay neutral."""


def classify(result, *, research=False, verification=False):
    error = result.get("runtime_error", {})
    phase, kind = error.get("phase", "unknown"), error.get("kind", "unknown")
    terminal = result.get("terminal_status", "")
    if research or verification:
        return {"attributable": False, "category": "research" if research else "verification", "phase": phase}
    if phase in ("environment", "preflight", "contract") or kind in ("environment_denied", "environment_blocked", "contract_blocked"):
        return {"attributable": False, "category": "environment_or_contract", "phase": phase}
    if kind == "ticket_regression":
        return {"attributable": True, "category": "ticket_regression", "phase": phase}
    if kind in ("baseline_regression", "timeout", "undetermined", "task_verify", "evidence_contract", "unsupported_evidence"):
        return {"attributable": False, "category": kind, "phase": phase}
    if kind == "productive_timeout" or terminal == "step_budget_exceeded":
        return {"attributable": True, "category": "agent_budget", "phase": phase}
    if terminal == "execution_timeout" and result.get("actions_used", 0):
        return {"attributable": True, "category": "agent_deadline", "phase": phase}
    if phase == "pre_commit_audit" and error.get("code") in (2, 4, 5, 7, 8):
        return {"attributable": True, "category": "scope_or_audit", "phase": phase}
    return {"attributable": False, "category": "unknown", "phase": phase}

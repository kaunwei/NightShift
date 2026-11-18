"""Versioned maintenance declarations checked against trusted ticket authority."""
import json
from pathlib import Path
import re
import subprocess
import case_inventory
import ticket_policy

ACTIONS = {"rename", "merge", "migrate", "correct", "retire", "reintroduce"}


def identities(value, name, empty=False):
    if not isinstance(value, list) or (not value and not empty) or any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value):
        raise ValueError("maintenance requires unique " + name)
    return set(value)


def read_records(root, directory=".nightshift/changes"):
    if not isinstance(directory, str):
        raise ValueError("maintenance records directory must be a string")
    directory = Path(directory)
    if directory.is_absolute() or ".." in directory.parts or ".git" in directory.parts:
        raise ValueError("maintenance records require a safe relative directory")
    base = root / directory
    if base.is_symlink() or not base.resolve().is_relative_to(root):
        raise ValueError("unsafe maintenance directory")
    records = {}
    for path in sorted(base.glob("*.json")):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("unsafe maintenance record")
        record = json.loads(path.read_text())
        if not isinstance(record, dict):
            raise ValueError("maintenance record must be an object")
        identity = record.get("id")
        if record.get("version") != 1 or not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identity) or path.stem != identity or identity in records:
            raise ValueError("invalid maintenance record identity/version")
        records[identity] = (path, record)
    return records


def pending_removal(identity, records):
    """Find the unique unconsumed removal in the immutable baseline history."""
    removals = {key for key, (_, rec) in records.items()
                if identity in rec.get("old_cases", []) and identity not in rec.get("new_cases", [])}
    consumptions = [rec.get("predecessor_change") for _, rec in records.values()
                    if rec.get("action") == "reintroduce" and identity in rec.get("new_cases", [])]
    consumed = set(consumptions)
    if len(consumed) != len(consumptions):
        raise ValueError("ambiguous historical reintroduction lineage")
    if not consumed <= removals:
        raise ValueError("invalid historical reintroduction lineage")
    if not removals:
        return None
    tips = removals - consumed
    if len(tips) != 1:
        raise ValueError("ambiguous or consumed reintroduction predecessor: " + identity)
    return next(iter(tips))


def assess(root, base, title, inventory_config, *, deadline=None):
    root = Path(root).resolve()
    baseline = case_inventory.collect(root, inventory_config, base, deadline=deadline)
    candidate = case_inventory.collect(root, inventory_config, deadline=deadline)
    diff = case_inventory.compare(baseline, candidate)
    old = case_inventory.validate_cases(baseline["cases"])
    new = case_inventory.validate_cases(candidate["cases"])
    approved = {x.strip() for x in ticket_policy.field(title, "MAINTENANCE").split(",") if x.strip()}
    decisions = {x.strip() for x in ticket_policy.field(title, "DECISIONS").split(",") if x.strip()}
    records = read_records(root, inventory_config.get("records", ".nightshift/changes"))
    directory = inventory_config.get("records", ".nightshift/changes")
    historical = case_inventory.git(root, "ls-tree", "-r", "--name-only", base, "--", directory).decode().splitlines()
    for name in historical:
        if name.endswith(".json") and not (root / name).is_file():
            raise ValueError("accepted maintenance records cannot disappear")
    selected, covered, required, history = [], set(), set(), {}
    for identity, (path, record) in records.items():
        relative = path.relative_to(root).as_posix()
        if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative]).returncode == 0:
            raise ValueError("maintenance records must be delivered in Git")
        previous = subprocess.run(["git", "-C", str(root), "show", f"{base}:{relative}"], capture_output=True)
        if previous.returncode == 0:
            if previous.stdout != path.read_bytes():
                raise ValueError("accepted maintenance records are immutable; use a new change ID")
            if identity in approved:
                raise ValueError("maintenance change was already present at baseline")
            history[identity] = (path, record)
            continue
        if identity not in approved:
            raise ValueError("unauthorized MAINTENANCE change: " + identity)
        if not isinstance(record.get("decision_ref"), str) or record["decision_ref"] not in decisions or not isinstance(record.get("reason"), str) or not record["reason"].strip():
            raise ValueError("maintenance requires a ticket-authorized decision and reason")
        action = record.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError("unsupported maintenance action: " + str(action))
        reintroducing = action == "reintroduce"
        before = identities(record.get("old_cases"), "old_cases", empty=reintroducing)
        retiring = action == "retire"
        after = identities(record.get("new_cases"), "new_cases", empty=retiring)
        if reintroducing:
            predecessor_id = record.get("predecessor_change")
            predecessor = records.get(predecessor_id) if isinstance(predecessor_id, str) else None
            if before or len(after) != 1 or after & old.keys() or not predecessor or not after <= (set(predecessor[1].get("old_cases", [])) - set(predecessor[1].get("new_cases", []))):
                raise ValueError("reintroduction requires a historical removal and one newly discovered ID")
            prior_path = predecessor[0].relative_to(root).as_posix()
            prior = subprocess.run(["git", "-C", str(root), "show", f"{base}:{prior_path}"], capture_output=True)
            if prior.returncode or prior.stdout != predecessor[0].read_bytes():
                raise ValueError("reintroduction predecessor must already exist at baseline")
        verification = identities(record.get("verification_cases", []), "verification_cases", empty=True)
        if not verification <= new.keys():
            raise ValueError("maintenance verification case is absent")
        required.update(verification)
        if retiring:
            if after or not isinstance(record.get("removed_requirement"), str) or not record["removed_requirement"].strip():
                raise ValueError("retire requires a removed requirement and no replacement")
            verify = ticket_policy.field(title, "VERIFY")
            reason = record.get("no_remaining_reason")
            if not verification and (not isinstance(reason, str) or not reason.strip() or not verify or verify.lower() in ("none", "report_only")):
                raise ValueError("retire requires remaining verification or a reason and executable VERIFY")
        if not before <= old.keys() or not after <= new.keys():
            raise ValueError("maintenance case is absent from baseline or candidate inventory")
        if action in ("migrate", "correct") and before != after:
            raise ValueError("observation migration/correction must preserve canonical IDs")
        if action == "rename" and (len(before) != 1 or len(after) != 1 or before & after):
            raise ValueError("rename requires distinct one-to-one IDs")
        if action == "merge" and len(before) < 2:
            raise ValueError("merge requires multiple original cases")
        vanished = before - after
        if not vanished <= set(diff["removed"]):
            raise ValueError("replaced cases must actually disappear")
        if covered & vanished:
            raise ValueError("ambiguous maintenance coverage for disappearing cases")
        scenarios = record.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            raise ValueError("maintenance requires concrete scenario mappings")
        scenario_before, scenario_after = set(), set()
        for scenario in scenarios:
            if not isinstance(scenario, dict) or not isinstance(scenario.get("name"), str) or not scenario["name"].strip():
                raise ValueError("maintenance scenario requires a name")
            a = identities(scenario.get("before"), "scenario before", empty=reintroducing)
            b = identities(scenario.get("after"), "scenario after", empty=retiring)
            if retiring and (b or scenario.get("removed") is not True):
                raise ValueError("retirement scenarios must explicitly record removed behavior")
            if not a <= before or not b <= after:
                raise ValueError("scenario refers outside the declared case relation")
            scenario_before.update(a)
            scenario_after.update(b)
        if scenario_before != before or scenario_after != after:
            raise ValueError("maintenance scenarios omit declared cases")
        covered.update(vanished)
        required.update(after)
        selected.append(record)
    if approved != {r["id"] for r in selected}:
        raise ValueError("MAINTENANCE requires a new record for every authorized change")
    if set(diff["removed"]) != covered:
        raise ValueError("unauthorized case disappearance: " + ", ".join(sorted(set(diff["removed"]) - covered)))
    for identity in diff["added"]:
        predecessor = pending_removal(identity, history)
        if predecessor is not None:
            births = [c for c in selected if c["action"] == "reintroduce" and identity in c["new_cases"]]
            if len(births) != 1 or births[0].get("predecessor_change") != predecessor:
                raise ValueError("recreated ID requires exactly one lineage event with the unconsumed predecessor: " + identity)
    import case_traceability
    traceability = case_traceability.validate_change(root, base, diff, title, selected)
    previous_relations = case_traceability.model(root, base)["cases"]
    current_relations = case_traceability.model(root)["cases"]
    relations = {"before": previous_relations, "after": current_relations}
    return {**diff, "changes": selected, "required": sorted(required), "traceability": traceability, "relations": relations}


def verify_execution(plan, executed):
    inventory = {c["id"]: c for c in plan["candidate"]["cases"]}
    for identity in plan["required"]:
        actual = executed.get(identity, {})
        if actual.get("status") != "passed" or any(actual.get(k) != inventory[identity][k] for k in ("source", "fingerprint")):
            raise ValueError("maintenance replacement did not execute with matching evidence: " + identity)


def accepted_receipt(plan, commit, task, event, evidence):
    """Only the runtime's committed/accepted path calls this; no new state store."""
    import hashlib
    if not plan or not plan.get("changes"):
        return None
    if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40,64}", commit):
        raise ValueError("maintenance acceptance requires a committed revision")
    changes = sorted(c["id"] for c in plan["changes"])
    identity = hashlib.sha256(json.dumps([task, event, commit, changes]).encode()).hexdigest()
    return {"version": 1, "id": identity, "status": "accepted", "task": task,
            "change_ids": changes, "base_revision": plan["baseline"]["revision"], "commit": commit,
            "candidate_input_digest": plan["candidate"]["input_digest"],
            "provider_digest": plan["candidate"]["provider_digest"],
            "evidence": evidence, "relations": plan.get("relations", {})}


def failure_disposition(active, result):
    """Mechanical observations are evidence; semantic resolution stays with Planner."""
    error = result.get("runtime_error", {})
    kind = error.get("kind", "unknown")
    observations = {"ticket_regression": "candidate_failed_baseline_passed_or_new_case",
                    "baseline_regression": "baseline_also_failed", "timeout": "execution_timeout",
                    "evidence_contract": "incomplete_or_invalid_evidence"}
    evidence = error.get("evidence", {})
    proposal = result.get("maintenance_proposal") or {}
    if not isinstance(proposal, dict):
        proposal = {}
    failed = evidence.get("failed_cases", []) if isinstance(evidence, dict) else []
    relation_sets = proposal.get("relations", {})
    relations = relation_sets.get("after", {}) if isinstance(relation_sets, dict) else {}
    if not isinstance(relations, dict):
        relations = {}
    requirements = {identity: relations[identity]["verifies"] for identity in failed if identity in relations}
    return {"version": 1, "task": active.get("task_id"), "base_revision": active.get("base"),
            "requirements": requirements,
            "phase": error.get("phase", "unknown"), "runtime_kind": kind,
            "observation": observations.get(kind, kind), "resolution": "undetermined",
            "decision_required": True, "evidence": evidence, "message": error.get("message", result.get("diagnostic", "")),
            "maintenance_proposal": result.get("maintenance_proposal"),
            "next_step": "Check command/phase, execution conditions and accepted requirement decisions before repairing or retiring a case."}

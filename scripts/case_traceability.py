#!/usr/bin/env python3
"""Versioned requirement/scenario relations; no authoritative query cache."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def document(root, name, revision=None):
    path = Path(root) / ".nightshift" / name
    if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("unsafe traceability document")
    if revision:
        result = subprocess.run(["git", "-C", str(root), "show", f"{revision}:.nightshift/{name}"], capture_output=True)
        if result.returncode:
            return None
        value = json.loads(result.stdout)
    elif path.exists():
        delivered = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", str(path.relative_to(root))])
        if delivered.returncode != 1:
            raise ValueError("traceability documents must be delivered in Git: " + name)
        value = json.loads(path.read_text())
    else:
        return None
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("traceability document requires version 1")
    return value


def model(root, revision=None):
    req_doc = document(root, "requirements.json", revision)
    case_doc = document(root, "coverage.json", revision)
    requirements, cases = {}, {}
    for req in (req_doc or {}).get("requirements", []):
        if not isinstance(req, dict) or not isinstance(req.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", req["id"]) or type(req.get("version")) is not int or req["version"] < 1:
            raise ValueError("invalid requirement identity/version")
        key = req["id"] + "@" + str(req["version"])
        if key in requirements or req.get("status") not in ("active", "retired") or any(not isinstance(req.get(k), str) or not req[k].strip() for k in ("behavior", "decision_ref")):
            raise ValueError("invalid or duplicate requirement: " + key)
        requirements[key] = req
    for key, req in requirements.items():
        previous = req.get("supersedes")
        lower = [r for r in requirements.values() if r["id"] == req["id"] and r["version"] < req["version"]]
        if lower:
            expected = req["id"] + "@" + str(max(r["version"] for r in lower))
            if previous != expected:
                raise ValueError("requirement version needs its immediate predecessor: " + key)
        if previous is not None:
            if not isinstance(previous, str) or previous not in requirements or requirements[previous]["id"] != req["id"] or requirements[previous]["version"] >= req["version"]:
                raise ValueError("unknown or non-ascending requirement predecessor: " + key)
            affected = req.get("affected_scenarios")
            if not isinstance(affected, list) or not affected or any(not isinstance(x, str) or not x for x in affected) or len(set(affected)) != len(affected):
                raise ValueError("requirement revision needs affected_scenarios")
    for case in (case_doc or {}).get("cases", []):
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in cases or not isinstance(case.get("generation"), str) or not case["generation"]:
            raise ValueError("invalid case identity/generation")
        relations = case.get("verifies")
        if not isinstance(relations, list) or not relations:
            raise ValueError("mapped case requires requirement/scenario relations")
        seen = set()
        for relation in relations:
            if not isinstance(relation, dict) or not isinstance(relation.get("scenario"), str) or not relation["scenario"]:
                raise ValueError("invalid case scenario")
            ref, scenario = relation.get("requirement"), relation["scenario"]
            if not isinstance(ref, str) or ref not in requirements:
                raise ValueError("unknown requirement: " + str(ref))
            if (ref, scenario) in seen:
                raise ValueError("duplicate requirement/scenario relation")
            seen.add((ref, scenario))
            if requirements[ref]["status"] != "active":
                raise ValueError("case references retired requirement: " + ref)
            for successor in requirements.values():
                predecessor = successor.get("supersedes")
                while predecessor:
                    if predecessor == ref and (scenario in successor["affected_scenarios"] or "*" in successor["affected_scenarios"]):
                        raise ValueError("stale requirement relation: " + ref + " / " + scenario)
                    predecessor = requirements[predecessor].get("supersedes")
        cases[case["id"]] = case
    return {"enabled": req_doc is not None or case_doc is not None, "requirements": requirements, "cases": cases}


def validate_change(root, base, diff, title, changes):
    import ticket_policy
    current, previous = model(root), model(root, base)
    if not current["enabled"]:
        if previous["enabled"]:
            raise ValueError("traceability cannot silently be disabled")
        return {"enabled": False, "mapped_cases": 0}
    decisions = {x.strip() for x in ticket_policy.field(title, "DECISIONS").split(",")}
    for ref, req in previous["requirements"].items():
        if current["requirements"].get(ref) != req:
            raise ValueError("requirement versions are immutable: " + ref)
    for ref in current["requirements"].keys() - previous["requirements"].keys():
        if current["requirements"][ref]["decision_ref"] not in decisions:
            raise ValueError("new requirement version requires ticket-authorized DECISIONS")
    inventory = {c["id"] for c in diff["candidate"]["cases"]}
    if not current["cases"].keys() <= inventory:
        raise ValueError("coverage refers to absent canonical cases")
    required = set(diff["added"]) | set(diff["modified"]) | (previous["cases"].keys() & inventory)
    if not required <= current["cases"].keys():
        raise ValueError("new/modified/mapped cases require requirement relations")
    for identity in previous["cases"].keys() & current["cases"].keys():
        if previous["cases"][identity]["generation"] != current["cases"][identity]["generation"]:
            raise ValueError("existing case generation cannot change without a removal/reintroduction")
    for change in changes:
        if change["action"] == "reintroduce":
            relation = current["cases"][change["new_cases"][0]]
            if relation.get("previous_change") != change["predecessor_change"] or relation["generation"] != change["id"]:
                raise ValueError("recreated ID requires explicit reintroduction lineage and a new generation")
    def retired(ref, scenario, decision=None):
        for successor in current["requirements"].values():
            if successor["status"] != "retired" or successor["decision_ref"] not in decisions or (decision is not None and successor["decision_ref"] != decision):
                continue
            if scenario is not None and scenario not in successor.get("affected_scenarios", []) and "*" not in successor.get("affected_scenarios", []):
                continue
            predecessor = successor.get("supersedes")
            while predecessor:
                if predecessor == ref:
                    return True
                predecessor = current["requirements"][predecessor].get("supersedes")
        return False
    def obligation(relation):
        return (current["requirements"][relation["requirement"]]["id"], relation["scenario"])
    protected = {obligation(relation) for case in current["cases"].values() for relation in case["verifies"]}
    for case in previous["cases"].values():
        for relation in case["verifies"]:
            if obligation(relation) not in protected and not retired(relation["requirement"], relation["scenario"]):
                raise ValueError("active requirement scenario lost coverage: " + str(obligation(relation)))
    for change in changes:
        replacements = set(change["new_cases"]) | set(change.get("verification_cases", []))
        covered = {obligation(relation) for identity in replacements if identity in current["cases"] for relation in current["cases"][identity]["verifies"]}
        for identity in change["old_cases"]:
            for relation in previous["cases"].get(identity, {}).get("verifies", []):
                if obligation(relation) not in covered and not retired(relation["requirement"], relation["scenario"], change["decision_ref"]):
                    raise ValueError("replacement/remaining verification omits an active scenario")
        if change["action"] == "rename":
            old_case = previous["cases"].get(change["old_cases"][0])
            new_case = current["cases"].get(change["new_cases"][0])
            if old_case and new_case and old_case["generation"] != new_case["generation"]:
                raise ValueError("rename/move must preserve case generation")
        if change["action"] == "retire":
            ref = change["removed_requirement"]
            if ref not in current["requirements"] or not retired(ref, None, change["decision_ref"]):
                raise ValueError("retire requires a matching authorized requirement retirement")
    return {"enabled": True, "mapped_cases": len(current["cases"])}


def query(root, action, identity=None, records_dir=".nightshift/changes"):
    value = model(root)
    if action == "check":
        return {"mapped_cases": len(value["cases"]), "requirements": len(value["requirements"]), "enabled": value["enabled"]}
    if action == "case":
        return value["cases"].get(identity, {"id": identity, "status": "legacy", "verifies": []})
    if action in ("requirement", "impact"):
        refs = {identity} if "@" in identity else {r for r, req in value["requirements"].items() if req["id"] == identity}
        if not refs or not refs <= value["requirements"].keys():
            raise ValueError("unknown requirement: " + identity)
        return {"requirements": sorted(refs), "cases": sorted(k for k, c in value["cases"].items() if any(r["requirement"] in refs for r in c["verifies"]))}
    if action == "lineage":
        import case_maintenance
        records = [v[1] for v in case_maintenance.read_records(Path(root).resolve(), records_dir).values()]
        # Historical imports describe past evidence; they are never runtime receipts.
        history = document(root, "history.json") or {"changes": []}
        records += history.get("changes", [])
        return {"id": identity, "generation": value["cases"].get(identity, {}).get("generation"),
                "changes": [r for r in records if identity in r.get("old_cases", []) + r.get("new_cases", [])]}
    raise ValueError("unknown traceability query")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--records", default=".nightshift/changes", help="match inventory.records for lineage queries")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check")
    for action in ("requirement", "case", "impact", "lineage"):
        sub.add_parser(action).add_argument("identity")
    args = parser.parse_args()
    try:
        print(json.dumps(query(args.root, args.action, getattr(args, "identity", None), args.records), indent=2))
    except (ValueError, OSError) as error:
        print("traceability error: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

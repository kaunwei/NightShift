"""Deterministic ticket evidence/effort contract, shared by claim and execution."""
from pathlib import Path
import re

FIELD_NAMES = ("LEVEL", "TARGET", "ACTION", "GOAL", "VERIFY", "FORBIDDEN_SHORTCUTS",
               "CONSTRAINTS", "DEPENDS_ON", "CASES", "EVIDENCE", "FILES")


def field(raw, key):
    if key not in FIELD_NAMES:
        raise ValueError(f"unknown task field: {key}")
    match = re.search(rf"(?:^|\|\s*){key}:\s*", raw)
    if not match:
        return ""
    rest = raw[match.end():]
    end = re.search(r"\s*\|\s*(?:" + "|".join(FIELD_NAMES) + r"):\s*", rest)
    return (rest[:end.start()] if end else rest).strip()


def is_verify(raw):
    return bool(re.search(r"\[VERIFY\]", raw.split("|", 1)[0], re.I))


def evidence_mode(raw):
    mode = field(raw, "EVIDENCE").upper() or "CHANGED"
    if mode not in ("CHANGED", "EXISTING"):
        raise ValueError("EVIDENCE must be CHANGED or EXISTING")
    if mode == "EXISTING":
        if not re.search(r"\[CODE:\s*REFACTOR\]", raw.split("|", 1)[0], re.I):
            raise ValueError("EVIDENCE EXISTING requires an explicit CODE: REFACTOR ticket")
        if not required_cases(raw):
            raise ValueError("EVIDENCE EXISTING requires nonempty CASES")
    return mode


def required_cases(raw):
    cases = [name.strip() for name in field(raw, "CASES").split(",") if name.strip()]
    if len(set(cases)) != len(cases):
        raise ValueError("CASES must contain unique IDs")
    return cases


def planned_files(raw):
    targets = {str(Path(name.strip())) for name in field(raw, "TARGET").split(",") if name.strip()}
    estimate = field(raw, "FILES")
    if estimate and (not re.fullmatch(r"[0-9]+", estimate) or int(estimate) < 1):
        raise ValueError("FILES must be a positive integer")
    return max(1, len(targets), int(estimate) if estimate else 0)


def validate(raw):
    mode = evidence_mode(raw)
    count = planned_files(raw)
    level = field(raw, "LEVEL")
    if level and level not in ("1", "2", "3"):
        raise ValueError("LEVEL must be 1, 2 or 3")
    if is_verify(raw):
        verify = field(raw, "VERIFY")
        if not verify or verify.lower() in ("none", "report_only"):
            raise ValueError("VERIFY tickets require an executable VERIFY command")
    return {"evidence": mode, "planned_files": count}


def preparation_base(worker, level):
    ladder = worker["step_base"]
    floor = worker.get("preparation_steps", ladder["L2"])
    return max(ladder[f"L{level}"], floor)

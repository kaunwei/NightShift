"""Deterministic, conservative Python source evidence for Explore runs."""
import ast
import hashlib
import json
from pathlib import Path
import re


def _module_name(rel):
    value = rel[:-3] if rel.endswith(".py") else rel
    value = value.replace("/", ".")
    return value[:-9] if value.endswith(".__init__") else value


def _import_targets(node, rel):
    module = _module_name(rel)
    package = module if rel.endswith("/__init__.py") or rel == "__init__.py" else module.rpartition(".")[0]
    targets = []
    if isinstance(node, ast.Import):
        targets.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        base = node.module or ""
        if node.level:
            parts = package.split(".") if package else []
            keep = max(0, len(parts) - node.level + 1)
            base = ".".join(parts[:keep] + ([base] if base else []))
        if base:
            targets.append(base)
            targets.extend(".".join(filter(None, (base, alias.name))) for alias in node.names)
    return targets


def build_static_evidence(root, paths, task_text="", max_seeds=4):
    """Index Python definitions, explicit imports, conservative name-call matches and leads.

    Call edges resolve only bare calls whose function name has exactly one definition in
    the indexed source set. Attribute calls, dynamic dispatch, and ambiguous names remain
    unresolved; these facts describe syntax and do not claim runtime execution.
    """
    root = Path(root)
    task_mentions_tests = bool(re.search(r"\btests?\b|testing|test suite", task_text.lower()))
    def is_test_path(rel):
        parts = Path(rel).parts
        return (bool(parts and parts[0].lower() in {"test", "tests"})
                or Path(rel).name.lower().startswith("test_"))
    available = sorted({Path(path).as_posix() for path in paths
                        if str(path).endswith(".py")
                        and (task_mentions_tests or not is_test_path(Path(path).as_posix()))})
    module_candidates = {}
    for rel in available:
        module_candidates.setdefault(_module_name(rel), set()).add(rel)

    def resolve_module(module):
        candidates = module_candidates.get(module, set())
        return next(iter(candidates)) if len(candidates) == 1 else None

    files = {}
    definitions_by_name = {}
    imports = []
    call_sites = []
    for rel in available:
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        definitions = []
        local_imports = []
        local_calls = []

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.scope = []

            def visit_FunctionDef(self, node):
                qualified = ".".join(self.scope + [node.name])
                item = {"name": node.name, "qualified": qualified,
                        "line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno)}
                definitions.append(item)
                definitions_by_name.setdefault(node.name, []).append((rel, item["line"], qualified))
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                qualified = ".".join(self.scope + [node.name])
                definitions.append({"name": node.name, "qualified": qualified,
                                    "line": node.lineno,
                                    "end_line": getattr(node, "end_lineno", node.lineno)})
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()

            def visit_Import(self, node):
                for target in _import_targets(node, rel):
                    resolved = resolve_module(target)
                    if resolved:
                        local_imports.append({"source": rel, "line": node.lineno,
                                              "target": resolved})
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                for target in _import_targets(node, rel):
                    resolved = resolve_module(target)
                    if resolved:
                        local_imports.append({"source": rel, "line": node.lineno,
                                              "target": resolved})
                self.generic_visit(node)

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    local_calls.append({"source": rel, "line": node.lineno,
                                       "caller": ".".join(self.scope) or "<module>",
                                       "callee": node.func.id})
                self.generic_visit(node)

        Visitor().visit(tree)
        files[rel] = {"path": rel, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "definitions": sorted(definitions, key=lambda item: (item["line"], item["qualified"]))}
        imports.extend(local_imports)
        call_sites.extend(local_calls)

    calls, unresolved = [], []
    for site in call_sites:
        candidates = definitions_by_name.get(site["callee"], [])
        if len(candidates) == 1:
            target, target_line, _qualified = candidates[0]
            calls.append({**site, "target": target, "target_line": target_line,
                          "resolution": "unique-name-match"})
        elif candidates:
            unresolved.append({**site, "reason": "ambiguous-name",
                               "candidates": sorted({candidate[0] for candidate in candidates})})
        else:
            unresolved.append({**site, "reason": "no-indexed-definition", "candidates": []})

    generic_terms = {"adapter", "explore", "report", "source", "evidence", "task",
                     "file", "files", "flow", "research", "investigation"}
    terms = {term for term in re.findall(r"[a-z0-9_]+", task_text.lower())
             if len(term) > 3 and term not in generic_terms}
    def score(rel):
        haystack = rel.lower() + " " + " ".join(item["name"].lower()
                                                     for item in files.get(rel, {}).get("definitions", []))
        return sum(term in haystack for term in terms)
    ranked = sorted(files, key=lambda rel: (-score(rel), rel))
    seeds = [rel for rel in ranked if score(rel)][:max(1, max_seeds)]
    seed_set = set(seeds)
    selected = set(seed_set)
    edges = [(item["source"], item["target"]) for item in imports + calls]
    for source, target in edges:
        if source in seed_set or target in seed_set:
            selected.update((source, target))
    return {"files": files, "imports": sorted(imports, key=lambda item: (item["source"], item["line"], item["target"])),
            "calls": sorted(calls, key=lambda item: (item["source"], item["line"], item["target"])),
            "unresolved_calls": sorted(unresolved, key=lambda item: (item["source"], item["line"])),
            "seeds": seeds, "selected": sorted(selected)}


def append_ledger(path, record):
    """Append one complete JSON evidence record without rewriting prior records."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()


def static_context(evidence, summaries):
    """Render a bounded, reproducible index for model calls; no model-authored memory."""
    facts = ["STATIC SOURCE FACTS (syntax only; not runtime behavior):"]
    selected = set(evidence["selected"])
    for item in evidence["imports"]:
        if item["source"] in selected or item["target"] in selected:
            facts.append(f"- Import syntax: {item['source']}#L{item['line']} -> {item['target']}")
    for item in evidence["calls"]:
        if item["source"] in selected or item["target"] in selected:
            facts.append(f"- Bare name call (unique name match, not binding proof): "
                         f"{item['source']}#{item['caller']}#L{item['line']} -> "
                         f"{item['callee']} at {item['target']}#L{item['target_line']}")
    for item in evidence["unresolved_calls"]:
        if item["source"] in selected:
            facts.append(f"- Unresolved bare call: {item['source']}#{item['caller']}#L{item['line']} "
                         f"-> {item['callee']} ({item['reason']})")
    facts.append("INSPECTED SUMMARIES (model drafts, source-check before treating as facts):")
    facts.extend(f"- {path}: {summary[:220]}" for path, summary in summaries.items())
    return "\n".join(facts)


def render_static_report(task_id, commit, task_title, evidence, summaries, inspected_spans):
    """Render a compact report from parsed edges and read spans, without model synthesis."""
    def observed(path, line):
        return any(start <= line <= end for start, end in inspected_spans.get(path, []))

    def pointer(path, line):
        return f"`{path}#L{line}`"

    def first_anchor(paths=None):
        allowed = set(paths or summaries)
        for path in summaries:
            if path not in allowed:
                continue
            for item in evidence["files"].get(path, {}).get("definitions", []):
                if observed(path, item["line"]):
                    return path, item["line"]
        for path in summaries:
            if path in allowed and inspected_spans.get(path):
                return path, inspected_spans[path][0][0]
        return None

    def preferred_anchor(paths, names):
        allowed = set(paths)
        for path in summaries:
            if path not in allowed:
                continue
            for item in evidence["files"].get(path, {}).get("definitions", []):
                if item["name"] in names:
                    for start, end in inspected_spans.get(path, []):
                        if item["line"] <= end and item["end_line"] >= start:
                            return path, max(item["line"], start)
        return first_anchor(paths)

    imports = [item for item in evidence["imports"]
               if item["source"] in summaries and observed(item["source"], item["line"])]
    calls = [item for item in evidence["calls"]
             if item["source"] in summaries and observed(item["source"], item["line"])]
    unresolved = [item for item in evidence["unresolved_calls"]
                  if item["source"] in summaries and observed(item["source"], item["line"])]
    ambiguous_count = sum(item["reason"] == "ambiguous-name" for item in unresolved)
    no_indexed_target_count = len(unresolved) - ambiguous_count
    anchor = first_anchor()
    inspected = ", ".join(f"`{path}`" for path in summaries)
    coverage = {path: ("partial" if "PARTIAL" in summary else "full")
                for path, summary in summaries.items()}
    partial = [path for path, kind in coverage.items() if kind == "partial"]
    chunks_read = sum(len(ranges) for ranges in inspected_spans.values())

    lines = [f"<!-- REPORT_META: Task={task_id} | Commit={commit} -->", "",
             "# Explore Report", "", "## Topology", ""]
    if anchor:
        lines.append(f"- Python AST indexed {len(evidence['files'])} files; inspected "
                     f"{len(summaries)} source files across {chunks_read} source windows. "
                     f"Selected: {inspected}. Anchor: {pointer(*anchor)}.")
    else:
        lines.append(f"- Python AST indexed {len(evidence['files'])} files; inspected "
                     f"{len(summaries)} source files across {chunks_read} source windows: {inspected}.")

    lines.extend(["", "## Static Caller Leads", ""])
    caller_facts = []
    for item in imports:
        caller_facts.append(
            f"- {pointer(item['source'], item['line'])} imports `{item['target']}` (static import syntax).")
    for item in calls:
        caller_facts.append(
            f"- `{item['source']}::{item['caller']}` calls `{item['callee']}` at "
            f"{pointer(item['source'], item['line'])}; unique-name match only; binding is unproven "
            f"(indexed target `{item['target']}::{item['callee']}`).")
    lines.extend(caller_facts[:5] or [
        "- No import or uniquely matched bare-call edges occurred inside the source windows read."])

    lines.extend(["", "## Coupling Bottlenecks", ""])
    edges_by_source = {}
    for item in imports + calls:
        edges_by_source.setdefault(item["source"], []).append(item)
    if edges_by_source:
        hot_path = sorted(edges_by_source, key=lambda path: (-len(edges_by_source[path]), path))[0]
        hot_edge = edges_by_source[hot_path][0]
        citation = pointer(hot_path, hot_edge["line"])
        lines.append(f"- `{hot_path}` has the most observed static edges "
                     f"({len(edges_by_source[hot_path])}) in read windows, including {citation}; "
                     "this measures syntax, not runtime traffic.")
    else:
        lines.append("- No static edge concentration was measurable in the source windows read.")
    lines.append(f"- {len(unresolved)} bare-call sites had no unique local target in read windows: "
                 f"{ambiguous_count} ambiguous and {no_indexed_target_count} with no indexed "
                 "target (often builtins or external APIs); attribute calls, dynamic dispatch, "
                 "and non-Python links are outside this index.")

    lines.extend(["", "## Expand–Migrate–Contract Matrix", "",
                  "| Phase | Bounded action | Evidence gate |", "|---|---|---|"])
    expand_anchor = preferred_anchor(["scripts/adapters/explore_evidence.py"],
                                     {"build_static_evidence", "append_ledger"}) or anchor
    migrate_anchor = preferred_anchor(["scripts/adapters/explore_evidence.py"],
                                      {"render_static_report"}) or anchor
    contract_anchor = preferred_anchor(["scripts/adapters/explore_evidence.py"],
                                       {"render_static_report"}) or anchor
    expand_cite = f" {pointer(*expand_anchor)}" if expand_anchor else ""
    migrate_cite = f" {pointer(*migrate_anchor)}" if migrate_anchor else ""
    contract_cite = f" {pointer(*contract_anchor)}" if contract_anchor else ""
    lines.append(f"| Expand | Keep syntax edges, unresolved calls, source hashes, and read spans in the ledger.{expand_cite} | Repeatable index and complete spans. |")
    lines.append(f"| Migrate | Shadow-compare graph-selected files and caller coverage with reviewed Explore reports.{migrate_cite} | No lost high-value source edges. |")
    lines.append(f"| Contract | Retire model-authored final synthesis only after repeated reports pass Planner review.{contract_cite} | Stable coverage and zero unsupported claims. |")

    lines.extend(["", "## Evidence and Unknowns", "",
                  f"- {chunks_read} exact source windows were read; partial files: "
                  f"{', '.join(f'`{path}`' for path in partial) if partial else 'none'}. "
                  f"{len(summaries)} model notes remain unverified in the execution evidence ledger.",
                  f"- Task: {task_title}. Name matches are static heuristics; dynamic callers, "
                  "runtime behavior, and semantic claim entailment remain unverified.", ""])
    return "\n".join(lines)

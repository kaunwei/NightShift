# NightShift Code Index

This directory owns the reusable index CLI, parser registry, and its runtime dependencies. A consuming repository owns `nightshift/code-index.toml`, which selects source paths and labels tool-owned code separately from product code. Generated artifacts live under the ignored `nightshift/.scratch/code-index/` directory.

## Supported parsers

The CLI uses Tree-sitter grammars from the installed Python package `tree-sitter-language-pack` for Swift, Python, JavaScript, TypeScript/TSX, Go, Rust, C, C++, Java, Bash, Make, and CMake. Add a language by extending `languages.json` with its file extensions and syntax node categories; Tree-sitter handles parsing, so language grammar implementation stays in the dependency. Other parser-pack languages can be added as registry entries with tests.

Evidence labels are `ast:declaration`, `ast:import`, and `ast:identifier-reference`. References and caller matches are syntax-level leads, not compiler-resolved bindings. Parser recovery is included in diagnostics.

## Setup

From the consuming repository root, set up the private parser environment once:

```sh
nightshift/tools/setup.sh
```

This creates an ignored `.venv` inside this tool directory and installs the pinned `tree-sitter-language-pack` Python dependency there with pip. The project does not acquire Python packages in its own runtime environment.

On Windows, run `powershell -ExecutionPolicy Bypass -File nightshift/tools/setup.ps1` to install parser dependencies.

## CLI

```sh
python3 nightshift/worker_runtime.py code-index query callers stop --scope project --format compact
```

Windows:

```bat
python nightshift/worker_runtime.py code-index query callers stop --scope project --format compact
```

The script rejects building/querying when indexed sources or settings are dirty, preserving the existing cache. With clean indexed inputs, it reuses an existing index for the same HEAD without rewriting it; a missing index or different Git hash triggers a build. Worker code commits refresh the index automatically. Agents may call `ensure` when useful; the freshness decision stays inside the script. Use `build` after a rollback; `build` and `ensure` use the same clean-input and Git-hash checks:

```sh
python3 nightshift/worker_runtime.py code-index build
```

```bat
python nightshift/worker_runtime.py code-index build
```

Other query examples:

```sh
python3 nightshift/worker_runtime.py code-index query symbol PracticeTracker --scope project --format compact
python3 nightshift/worker_runtime.py code-index query references PracticeTracker --scope project --format compact
python3 nightshift/worker_runtime.py code-index query callers stop --scope project --format compact
```

Use `--scope tool` when changing the installed indexer, `--scope project` for application or repository code, and `--scope all` for a cross-boundary change. Queries return source paths, line/column, language, scope, evidence type, generation identity, and explicit truncation/coverage status.

The Python implementation lives in `index.py` and is called by `worker_runtime.py`; it has no separate launcher directory. The parser environment remains private to `nightshift/tools/.venv`.

## Generated files

- `nightshift/.scratch/code-index/INDEX.md`: agent navigation map, bounded to 8 KiB.
  It lists HEAD, scoped source paths and up to three definitions per file, with symbol kind,
  owner-qualified name and line number. File paths and first symbols take priority within
  the budget; omitted file counts and symbol limits are explicit. Planner and Worker read this map.
  Call/reference counts are returned only by on-demand queries.
- `nightshift/.scratch/code-index/index.json`: compact script-owned file inventory with up to three definitions per file.
  Complete symbol, import, reference and caller evidence is parsed on demand rather than stored.

Build JSON returns both `summary_path` and `index_path`. Each checkout has its own files.
Detailed queries remain bounded by `--limit` and can return `--format compact` for agents.

Symbol queries accept either simple names or owner-qualified names such as
`HarmonyCoordinator.reset`. These names describe syntax scopes, not compiler bindings.
Reference/caller queries use simple names and return source locations plus a distinct `reference_files` count;
symbol queries may return same-name call candidates. The compact navigation map stores no counts.

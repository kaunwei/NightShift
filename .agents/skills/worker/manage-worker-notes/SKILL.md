---
name: manage-worker-notes
description: "How the background worker reads and maintains repository quirks, build tips, and lessons learned in .worker.notes.md."
---

# Manage Worker Notes

Maintain a local cheat sheet (`.worker.notes.md`) to preserve project-specific build quirks, tool paths, and compiler flags across stateless runs.

## When to Consult `.worker.notes.md`
- **Start of every task**: Check if `.worker.notes.md` exists. Follow project-specific flags and paths.

## When to Update `.worker.notes.md`
- When you discover a non-obvious repository quirk (e.g., hidden env vars, custom build targets).
- When an unexpected linker dependency or header ordering is required.
- Append a concise 1-2 line tip under the relevant section. Keep the file compact (< 50 lines).

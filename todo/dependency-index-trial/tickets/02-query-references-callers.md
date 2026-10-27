# 02: Recover task-relevant Swift references and caller evidence

**What to build:** Through the same script interface, agents can ask which source references a symbol and which statically resolvable callers may be affected, including relevant tests and cross-module consumers. They can distinguish verified semantic relationships from syntactic leads and unresolved cases.

**Blocked by:** 01 — Query Swift module structure and symbol definitions.

**Status:** draft — pending breakdown and test-seam approval

- [ ] A definition-to-references query works end to end for independently checked Matronome coordinator examples and their relevant tests.
- [ ] Results distinguish semantic resolution, syntactic leads, and unresolved scope; a reference is not automatically classified as a call.
- [ ] Same-name matches, overloads, protocol dispatch, and dynamic calls are not presented as more certain than the selected tooling supports.
- [ ] No matches or failed resolution cannot be presented as proof that no callers exist.
- [ ] Output remains bounded and points to source evidence; agents can deliberately request additional results.
- [ ] Public CLI tests check required relationships and false-positive exclusions using independent expected answers, without paid models.
- [ ] Operator instructions remain limited to index location, commands, and result status interpretation.

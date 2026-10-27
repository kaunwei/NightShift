# 04: Replay identical Planner tickets with isolated Worker stages and restoration

**What to build:** A manual trial runner can execute and preserve a baseline Planner workflow from a pinned product revision: one Planner session produces an exploration Worker task followed by a small-change Worker task. It can replay the same Planner inputs in a fresh arm, collect role-specific evidence, and undo every trial product change. This is independently demonstrable with fake agents before an index exists.

**Blocked by:** None (can start immediately).

**Status:** draft — pending breakdown and test-seam approval

- [ ] Freeze one Matronome exploration objective and one small-change objective with independent reference relationships and a concrete change verification command.
- [ ] Store exact Planner ticket bytes/hashes and reject comparison inputs that differ. Preserve derived Worker tickets as outcomes, without requiring them to match between arms.
- [ ] Pin the same initial product revision, model settings, and relevant environment for both arms; separate treatment/tool access metadata from identical task inputs.
- [ ] Record one fresh Planner session and two sequential Worker task runs per arm, with separate contexts/research artifacts so no arm inherits another arm's answers.
- [ ] Preserve role/stage transcripts, commands, verification, actual available usage, cached usage where exposed, timestamps, and source identity outside the product restoration boundary.
- [ ] Undo all trial product edits and candidate commits after each arm and verify exact baseline restoration before another arm, including failure-path cleanup.
- [ ] Protect pre-existing user work and the index tooling; refuse unsafe setup instead of resetting an unrelated checkout.
- [ ] Fake-agent CLI tests demonstrate replay, mismatched-ticket rejection, role attribution, missing usage, failures, artifact preservation, and restoration without consuming tokens.
- [ ] No live benchmark runs occur as part of the harness's mechanical tests.

# Local TDD Harness Trial Notes

Historical pilot: the standalone harness, guide and tests were retired because the production Worker does not use them. These observations remain as experiment history.

## Goal

Evaluate whether `nightshift/local_tdd.py` can keep the 2B, 40K-context `minicpm_local` Codex profile on a confirmed TDD seam, including a real Swift package task rather than only a toy example.

## Setup

- Matronome baseline: `d1e4014b729c955ba472f8da4046d8cdd8f948de`.
- All live runs used a `git archive HEAD` copy under `/private/tmp/matronome-local-tdd-pilot-20261025`; the original Matronome worktree was not edited.
- The installed Swift compiler and default macOS 27 SDK had mismatched patch versions. The isolated package test ran successfully after selecting the installed macOS 26.5 SDK and an external `/private/tmp` Clang module cache.
- A tiny Python `classify(0)` task completed one assertion RED and one GREEN with the fake/local harness cycle. This validates the basic orchestration only, not project-scale capability.

## Matronome Trial

Confirmed seam: `TapTempoCalculator.tap(at:)` returns `nil` and clears prior history on a backward timestamp, so later taps do not calculate from stale intervals.

Observed results:

1. The first ticket used `Tests/...` while Git records `tests/...`. The scope gate rejected the path spelling mismatch; correcting the ticket to the exact tracked casing resolved this setup mistake.
2. A subsequent RED test used the correct sequence and produced an assertion-level failure. GREEN changed the timeout condition to use `abs(timestamp - last) > timeoutInterval`. The focused test still failed on the first forward tap after the backward timestamp. The harness correctly stopped before accepting GREEN.
3. Another run authored a conflicting test expectation (the backward tap was expected to produce a tempo) and modified `nightshift/progress.log` under the repository's worker conventions. The scope gate rejected the auxiliary file change. This showed that an assertion failure alone does not prove the RED test matches the ticket.
4. A bounded GREEN-repair loop was implemented and passed a fake-agent test. The live Matronome attempt did not complete; later local turns repeatedly rewrote the test and were interrupted before a trustworthy harness verdict.
5. An optional `required_test_snippets` gate was added and tested with a fake agent. It rejects RED tests missing ticket-selected assertions before running tests or starting GREEN. The live attempt was interrupted before its result could establish whether the model follows the markers.

## Current Assessment

The harness provides useful deterministic protections: local-provider verification, isolated Codex configuration, file-scope checks, test immutability, assertion-only RED, optional contract snippets, and bounded failure-informed GREEN retries. It does not make the model reliably follow a task. In this Matronome trial the local model did not complete a valid RED/GREEN cycle, and the first valid RED led to an incorrect GREEN change.

The next useful experiment is to rerun the same seam with `required_test_snippets` mandatory for that ticket and a single GREEN retry, then measure elapsed time and whether the second GREEN turn fixes the exact failing assertion. Do not generalize from the toy pass or this single project seam to all TDD work.

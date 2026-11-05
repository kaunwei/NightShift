# Deterministic Explore Experiment Results

The source implementation is retired. This file records the measured outcomes separately from the design in [`DETERMINISTIC_EXPLORE_STRATEGY.md`](DETERMINISTIC_EXPLORE_STRATEGY.md). Exact scorecards and generated report artifacts are preserved in [`experiments/deterministic-explore`](experiments/deterministic-explore/README.md).

## Scores

| Run | Model / approach | Score | Main result |
|---|---|---:|---|
| Original Aider Explore | MiniCPM 2B + model-led RepoMap exploration and synthesis | 50/100 | Required artifacts passed mechanical shape checks, but the report contained fabricated and misattributed behavior. |
| Static-ledger Explore | MiniCPM 2B for bounded notes; deterministic file selection/evidence and report rendering | 89/100 | Four files, eight windows, nine in-span citations; one successful run. |
| Luna-low Explore | `gpt-6-luna`, low effort | 79/100 | Broader reading, but 11,086-byte report exceeded the 5 KB limit, omitted `03-micro.md`, and had one invalid pointer. |

## Interpretation

The static-ledger run's score gain came from deterministic evidence selection, citations, and report assembly; it does not show that the MiniCPM model gained general reasoning or coding ability. The 89/100 result is a single run and does not establish repeatability, semantic completeness, or token savings. Unsupported languages, dynamic dispatch, JSON registration relationships, and claim-to-source entailment remained open. The separate ported trial scored 50/100 and demonstrates that a good artifact shape can still contain unreliable claims.

## Archived generated outputs

- `experiments/deterministic-explore/PORTED-SUMMARY.md` and `PORTED-03-micro.md` preserve the actual report artifacts from the 50/100 run, including their factual errors.
- `experiments/deterministic-explore/LUNA-LOW-REPORT.md` preserves the Luna-low comparison output. Its citations refer to the historical source tree and should be read as a trial artifact, not current documentation.
- The scorecards preserve evaluation details and limitations. No archived report should be treated as source of truth for NightShift's current implementation.

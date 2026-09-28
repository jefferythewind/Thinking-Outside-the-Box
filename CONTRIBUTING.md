# Contributing

Keep the published tree focused on the three paper experiments. Develop new
ideas on a branch; write new outputs to ignored `runs/`. Do not overwrite
curated results or count repeated evaluations as independent samples.

Shared code lives in `src/totb/`, command-line tools in `scripts/`. Install
with `python -m pip install -e .`. Configurations describe reproduction;
archived metadata describes the original completed runs.

For inference or prompt changes, preserve token order and cache bounds,
check raw-window and scoring-cache visibility separately, and compare serial
and batched execution. Record seeds, model revisions, candidate IDs and
boundary indices. Supply actual context examples and matched controls.

Run the checks in [Reproducibility](docs/REPRODUCIBILITY.md). Do not commit
credentials, model weights or environments. Discussion and conclusions will
be synchronized with the paper separately from technical documentation.

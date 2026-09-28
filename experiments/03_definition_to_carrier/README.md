# Experiment 3: Definition-to-carrier gap

## Setup

A preamble states that the secret is the value following an arbitrary marker.
After D filler tokens, the carrier contains that marker and its code; tail
filler sets the independent code-relative offset. The question asks for the
secret code. Choices are scored from logits, not printed in the prompt.

| Setting | Value |
|---|---|
| Retained window | W=512 |
| Definition gaps D | 32, 64, 128, 256, 512, 768, 1024 |
| Code offsets | −32, 0, 32, 64, 128, 256 |
| Leading filler | 128 tokens |
| Rolling trials | 100/cell/model, data seed 2 |
| Controls | 20 saved prompts/cell/model for both controls, selection seed 2026 |
| Models | Five; BF16 except Glimmer NF4/BF16 compute |

Offsets are anchored to the code, not the end of the preamble. Offset 0
places the code at the start of the raw window. At −32 some definition tokens
may remain for short gaps. The marker prefix contributes additional tokens
between the definition and code. Full details: [Methods](../../docs/METHODS.md).

## Recorded results

- 21,000 Rolling-KV predictions and 8,400 control predictions; all cells complete.
- [Per-model cell summaries and intervals](results/summary.csv).
- [Seven-panel figure](figures/experiment3.png) · [PDF](figures/experiment3.pdf) · [plotted values and intervals](figures/experiment3.csv).
- `results/rolling/` and `results/controls/`: raw CSVs, metadata and exact compressed prompt IDs.
- `figures/rolling/` and `figures/controls/`: individual model plots.
- [Actual Qwen 0.5B contexts, one per cell](contexts/Qwen2.5-0.5B-Instruct.md).
- [Rolling configuration](configs/run.json), [control configuration](configs/controls.json), [artifact hashes](MANIFEST.json).

The two shared control panels are equal-weight means across five models;
they do not assert identical controls. All model-specific controls are retained.
The layout is a technical result display, subject to final paper styling.
Interpretation and conclusions are intentionally deferred.

## Reproduce

```bash
python scripts/run_experiment.py --experiment 3 --output runs/experiment3
SOURCE=runs/experiment3 OUTPUT=runs/experiment3_controls bash scripts/run_experiment3_controls.sh
python scripts/export_marker_contexts.py \
  --input experiments/03_definition_to_carrier/results/rolling/Qwen2.5-0.5B-Instruct.csv \
  --output runs/experiment3_contexts.md
python scripts/plot_experiment3.py --output runs/experiment3.png
```

The final command replots the published results by default; `--experiment-dir`
can point to another directory with the same `results/rolling` and
`results/controls` layout. Queue instructions and hardware prerequisites are
in [Reproducibility](../../docs/REPRODUCIBILITY.md). No old B-checkpoint or
Experiment 4 results are mixed into this fixed-grid package.

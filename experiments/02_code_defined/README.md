# Experiment 2: Longer code definition

## Setup

Task `code_defined`; W=512; offsets -10…+10; 100 trials/offset/model;
seed 1; neutral filler; four candidate tokens. Five models each evaluate
Last Window Only, Full Prompt and Rolling KV on the same prompts.
The defining phrase is `The secret code is defined by the following identifier:`.
The question is `What is the secret code?`; choices are scored, not printed.

Offset is final raw-window start minus code index. At 0 the code begins the
raw window; +1 still permits direct access in the final scoring cache;
+2 onward does not. See [Methods](../../docs/METHODS.md).

## Recorded results

- 2,100 prompts and 6,300 predictions per model; 31,500 total predictions.
- [Per-model, per-offset accuracy and Wilson intervals](results/summary.csv).
- [Combined figure](figures/experiment2_five_models_color.png) · [PDF](figures/experiment2_five_models_color.pdf).
- `results/`: five raw CSVs and original model metadata; no pilot results.
- [Actual Qwen 0.5B inputs at every offset](contexts/Qwen2.5-0.5B-Instruct.md):
  regenerated with the pinned tokenizer and checked against the official CSV.
- [Configuration](configs/run.json); [artifact hashes](MANIFEST.json).

Combined control curves are equal-weight model means. Individual controls
remain in the raw CSVs; confidence-interval definitions are in Methods.
Interpretation and discussion are reserved for the paper.

## Reproduce

After installation, from the repository root:

```bash
python scripts/run_experiment.py --experiment 2 --output runs/experiment2
python scripts/export_code_contexts.py \
  --input experiments/02_code_defined/results/Qwen2.5-0.5B-Instruct.csv \
  --output runs/experiment2_contexts.md
```

Use `--dry-run` to inspect configured commands. The launcher pins model
revisions, runs all five models sequentially, and generates individual and
combined plots. Exact settings and original execution paths are retained in
metadata; see [Reproducibility](../../docs/REPRODUCIBILITY.md).

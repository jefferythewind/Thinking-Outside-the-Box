# Experiment 1: Secret-code retrieval

## Setup

Task `code`; W=512; offsets -5…+5; 100 trials/offset/model;
seed 1; neutral filler; four candidate tokens. Five models each evaluate
Last Window Only, Full Prompt and Rolling KV on the same prompts.
The defining phrase is `The secret code is:`.
The question is `What is the secret code?`; choices are scored, not printed.

Offset is final raw-window start minus code index. At 0 the code begins the
raw window; +1 still permits direct access in the final scoring cache;
+2 onward does not. See [Methods](../../docs/METHODS.md).

## Recorded results

- 1,100 prompts and 3,300 predictions per model; 16,500 total predictions.
- [Per-model, per-offset accuracy and Wilson intervals](results/summary.csv).
- [Combined figure](figures/experiment1_five_models_color.png) · [PDF](figures/experiment1_five_models_color.pdf).
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
python scripts/run_experiment.py --experiment 1 --output runs/experiment1
python scripts/export_code_contexts.py \
  --input experiments/01_secret_code/results/Qwen2.5-0.5B-Instruct.csv \
  --output runs/experiment1_contexts.md
```

Use `--dry-run` to inspect configured commands. The launcher pins model
revisions, runs all five models sequentially, and generates individual and
combined plots. Exact settings and original execution paths are retained in
metadata; see [Reproducibility](../../docs/REPRODUCIBILITY.md).

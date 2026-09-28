# Reproducing the paper experiments

Run from the repository root after `python -m pip install -e .`. Follow
[model environment notes](MODELS.md), including optional Glimmer dependencies.
Write new outputs to ignored `runs/`, not curated `experiments/`.

```bash
python scripts/run_experiment.py --experiment 1 --output runs/experiment1
python scripts/run_experiment.py --experiment 2 --output runs/experiment2
python scripts/run_experiment.py --experiment 3 --output runs/experiment3
```

The launcher reads each experiment's `configs/run.json` and pinned revisions
from archived metadata, runs models sequentially and generates plots. Use
`--dry-run` to inspect commands, `--models Qwen2.5-0.5B-Instruct` for one model,
or `--glimmer-python PATH` for a separate environment. Full runs are substantial
GPU workloads. Existing output prefixes are rejected; there is no automatic resume.

## Experiment 3 controls

Controls read exact saved token IDs rather than regenerating prompts:

```bash
bash scripts/run_experiment3_controls.sh
```

Defaults use the published rolling results and write `runs/experiment3_controls`.
The queue waits for three idle GPU compute-process checks before each model.
This is not a reservation: do not start competing GPU jobs. It uses cached
weights (`HF_HUB_OFFLINE=1`); download models first. Override `PYTHON`,
`GLIMMER_PYTHON`, `OUTPUT`, and `SOURCE` as needed. For fresh rolling results,
set `SOURCE=runs/experiment3`. Compressed or uncompressed JSONL is accepted.
For a single model without the queue:

```bash
python scripts/run_marker_controls.py \
  --input experiments/03_definition_to_carrier/results/rolling/Qwen2.5-0.5B-Instruct.csv \
  --output runs/control_check/Qwen2.5-0.5B-Instruct.csv --trials 20
```

## Download-free CPU validation

```bash
python -m tests.validate_banded_cache
python -m tests.validate_glimmer_cache
python -m tests.validate_independent_batching
python -m tests.validate_artifacts
```

Checks cover independent banded attention, all-layer cache cropping,
serial/batched scores and grouping, artifact hashes, counts and control selection.
They do not assert pretrained task accuracy.

## Provenance

Curated results/metadata are immutable copies. Original local paths and hashes
are historical provenance, not portable commands. Each MANIFEST.json records
hashes at canonical paths. Compressed JSONL is lossless. Experiments 1/2 retain
seeds and indices for regeneration with pinned tokenizers; Experiment 3 retains
all input IDs. Model/task metadata must accompany any reused results.

Archived metadata records the original execution settings and local paths.
The current layout keeps the published experiments and validation data.
Numerical identity across different hardware or library versions is not
guaranteed. See [Methods](METHODS.md) for scoring and CIs.

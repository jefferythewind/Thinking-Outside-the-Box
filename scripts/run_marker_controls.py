from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm

from totb.model_utils import load_model
from totb.artifacts import read_trials
from plot_marker_heatmap import plot_heatmaps
from run_marker_grid import summarize_grid, write_csv
from totb.runner import score_full_prompt, score_last_window


def main():
    parser = argparse.ArgumentParser(description="Run only controls on a seeded subset of frozen marker prompts")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--selection-seed", type=int, default=2026)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    source, output = Path(args.input), Path(args.output)
    if args.trials < 1 or any(output.with_suffix(suffix).exists() for suffix in (".csv", ".metadata.json", ".trials.jsonl")):
        raise ValueError("Positive trials and a fresh output prefix are required")
    metadata_path = source.with_suffix(".metadata.json")
    trials_path = source.with_suffix(".trials.jsonl")
    metadata = json.loads(metadata_path.read_text())
    trials = read_trials(source)
    if not trials_path.exists():
        trials_path = source.with_suffix(".trials.jsonl.gz")
    with source.open() as handle:
        references = [row for row in csv.DictReader(handle) if row["condition"] == "rolling_kv"]
    previous = {int(row["trial"]): row for row in references}
    if len(previous) != len(references) or len(previous) != len(trials) or set(previous) != {trial["trial"] for trial in trials}:
        raise ValueError("Source must contain unique complete saved trials")
    cells = defaultdict(list)
    for trial in trials:
        row = previous[trial["trial"]]
        if (int(row["answer_token_id"]) != trial["answer_token_id"]
                or int(row["prompt_tokens"]) != len(trial["prompt_token_ids"])
                or list(map(int, row["candidate_token_ids"].split())) != trial["candidate_token_ids"]):
            raise ValueError("Saved prompt and result disagree")
        cells[int(row["definition_gap"]), int(row["boundary_offset"])].append(trial)
    generator = random.Random(args.selection_seed)
    selected = []
    for cell, group in sorted(cells.items()):
        if len(group) < args.trials:
            raise ValueError(f"Not enough source trials in {cell}")
        selected.extend(generator.sample(sorted(group, key=lambda trial: trial["trial"]), args.trials))
    print(f"Validated {len(cells)} cells; {len(selected)} prompts; {2 * len(selected)} control evaluations", flush=True)
    if args.validate_only:
        return
    loading = argparse.Namespace(**metadata["arguments"])
    loading.output = str(output)
    loading.revision = metadata["resolved_model_revision"]
    if not loading.revision:
        raise ValueError("Missing pinned source model revision")
    loading.batch_size = 1
    loading.control_trials = args.trials
    loading.full_prompt = True
    loading.control_only = True
    loading.selection_seed = args.selection_seed
    loading.source_artifacts = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (source, metadata_path, trials_path)}
    _, model = load_model(loading)
    control_metadata = json.loads(output.with_suffix(".metadata.json").read_text())
    control_metadata["cache_policy"] = "No rolling cache; independent uncached forward for each control"
    control_metadata["position_policy"] = "Each control starts at position zero; Last Window uses final W input IDs"
    control_metadata["batch_policy"] = "Serial independent control forwards"
    output.with_suffix(".metadata.json").write_text(json.dumps(control_metadata, indent=2) + "\n")
    output.with_suffix(".trials.jsonl").write_text("".join(json.dumps({**trial, "control_selected": True}) + "\n" for trial in selected))
    rows = []
    for trial in tqdm(selected, desc="control prompt pairs"):
        for condition in ("last_window", "full_prompt"):
            tokens, candidates = trial["prompt_token_ids"], trial["candidate_token_ids"]
            scores = (score_last_window(model, tokens, candidates, window_size=loading.window_size)
                      if condition == "last_window" else score_full_prompt(model, tokens, candidates))
            predicted = max(scores, key=scores.get)
            rows.append({**previous[trial["trial"]], "condition": condition,
                         "control_selected": 1, "independent_batch_size": 1,
                         "predicted_token_id": predicted, "correct": int(predicted == trial["answer_token_id"]),
                         "candidate_logprobs": json.dumps(scores), "selection_seed": args.selection_seed})
        write_csv(output, rows)
    output.with_suffix(".summary.txt").write_text(summarize_grid(rows) + "\n")
    plot_heatmaps(rows, output.with_suffix(".png"), f"{source.stem}: controls, n={args.trials}/cell")
    print(f"COMPLETE: {output}", flush=True)


if __name__ == "__main__":
    main()

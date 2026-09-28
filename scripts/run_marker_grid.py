from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from collections import defaultdict
from pathlib import Path
from statistics import mean

from tqdm import tqdm

from totb.evaluate import wilson_interval
from totb.marker_dataset import BOUNDARY_OFFSETS, build_marker_trials
from totb.runner import predict, score_full_prompt, score_last_window, score_rolling_kv
from totb.runner_batched import score_rolling_kv_batched
from totb.model_utils import add_model_options, load_model


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("batch-size must be positive")
    if args.batch_size > 1 and args.no_cache_position:
        raise ValueError("Independent batching requires token-by-token processing and absolute positions")
    if args.control_trials is not None and not 0 <= args.control_trials <= args.trials:
        raise ValueError("control-trials must be between 0 and trials")
    if args.output and Path(args.output).exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    tokenizer, model = load_model(args)

    definition_gaps = [value.strip() for value in args.definition_gaps.split(",")]
    boundary_offsets = [int(value) for value in args.boundary_offsets.split(",")]
    trials = build_marker_trials(
        tokenizer,
        num_trials=args.trials,
        window_size=args.window_size,
        definition_gaps=definition_gaps,
        boundary_offsets=boundary_offsets,
        num_choices=args.choices,
        filler_variant=args.filler,
        seed=args.seed,
        leading_filler_tokens=args.leading_filler_tokens,
        matched_trials=args.matched_trials,
    )

    control_limit = args.trials if args.control_trials is None else args.control_trials
    cell_counts = defaultdict(int)
    control_indices = set()
    for index, trial in enumerate(trials, start=1):
        cell = (trial.gap_checkpoint, trial.boundary_offset)
        cell_counts[cell] += 1
        if cell_counts[cell] <= control_limit:
            control_indices.add(index)
    if args.output:
        path = Path(args.output).with_suffix(".trials.jsonl")
        with path.open("w") as handle:
            for index, trial in enumerate(trials, start=1):
                handle.write(json.dumps({"trial": index, "control_selected": index in control_indices, **asdict(trial)}) + "\n")
    raw_rows: list[dict[str, object]] = []
    for completed, (index, trial, rolling_scores, actual_batch_size) in enumerate(
        tqdm(score_trials(model, trials, args), total=len(trials), desc="trials"), start=1,
    ):
        conditions = {
            "rolling_kv": rolling_scores,
        }
        if index in control_indices:
            conditions["last_window"] = score_last_window(model, trial.prompt_token_ids, trial.candidate_token_ids, window_size=args.window_size)
        if args.full_prompt and index in control_indices:
            conditions["full_prompt"] = score_full_prompt(model, trial.prompt_token_ids, trial.candidate_token_ids)
        for condition, scores in conditions.items():
            prediction = predict(scores, trial.answer_token_id)
            raw_rows.append(
                {
                    "trial": index,
                    "independent_batch_size": actual_batch_size if condition == "rolling_kv" else 1,
                    "matched_pair_id": trial.matched_pair_id,
                    "rolling_block_size": 1,
                    "choices": args.choices,
                    "condition": condition,
                    "definition_gap": trial.definition_gap,
                    "gap_checkpoint": trial.gap_checkpoint,
                    "first_inaccessible_gap": args.window_size - (trial.answer_token_index - trial.carrier_start_index),
                    "control_selected": int(index in control_indices),
                    "boundary_offset": trial.boundary_offset,
                    "offset_anchor": "answer_token",
                    "leading_filler_tokens": args.leading_filler_tokens,
                    "window_size": args.window_size,
                    "seed": args.seed,
                    "model": args.model,
                    "final_raw_start": len(trial.prompt_token_ids) - args.window_size,
                    "kv_scoring_start": max(0, len(trial.prompt_token_ids) - args.window_size - 1),
                    "raw_has_answer": int(trial.boundary_offset <= 0),
                    "kv_has_answer": int(trial.boundary_offset <= 1),
                    "answer_token_id": trial.answer_token_id,
                    "predicted_token_id": prediction.predicted_token_id,
                    "correct": int(prediction.correct),
                    "prompt_tokens": len(trial.prompt_token_ids),
                    "preamble_end_index": trial.preamble_end_index,
                    "carrier_block_start_index": trial.carrier_block_start_index,
                    "carrier_start_index": trial.carrier_start_index,
                    "answer_token_index": trial.answer_token_index,
                    "target_carrier_gap": trial.target_carrier_gap,
                    "last_definition_to_code_distance": trial.answer_token_index - trial.preamble_end_index + 1,
                    "code_attention_start": max(0, trial.answer_token_index - args.window_size),
                    "code_can_attend_definition": int(max(0, trial.answer_token_index - args.window_size) < trial.preamble_end_index),
                    "filler": args.filler,
                    "candidate_token_ids": " ".join(map(str, trial.candidate_token_ids)),
                    "marker_text": trial.marker_text,
                    "answer_text": trial.answer_text.strip(),
                    "carrier_rows": " | ".join(row.strip() for row in trial.carrier_rows),
                }
            )
        if args.output and completed % 10 == 0:
            write_csv(Path(args.output), raw_rows)

    print(summarize_grid(raw_rows))
    if args.output:
        write_csv(Path(args.output), raw_rows)


def score_trials(model, trials, args):
    if args.batch_size == 1:
        for index, trial in enumerate(trials, start=1):
            scores = score_rolling_kv(model, trial.prompt_token_ids, trial.candidate_token_ids,
                                     window_size=args.window_size, use_cache_position=not args.no_cache_position)
            yield index, trial, scores, 1
        return
    groups = defaultdict(list)
    for index, trial in enumerate(trials, start=1):
        groups[len(trial.prompt_token_ids)].append((index, trial))
    for length in sorted(groups):
        group = groups[length]
        for start in range(0, len(group), args.batch_size):
            batch = group[start:start + args.batch_size]
            scores = score_rolling_kv_batched(model, [trial.prompt_token_ids for index, trial in batch],
                                             [trial.candidate_token_ids for index, trial in batch],
                                             window_size=args.window_size)
            for (index, trial), score in zip(batch, scores, strict=True):
                yield index, trial, score, len(batch)


def summarize_grid(rows: list[dict[str, object]]) -> str:
    grouped: dict[tuple[str, str, int], list[bool]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["condition"]),
                str(row.get("gap_checkpoint", row["definition_gap"])),
                int(row["boundary_offset"]),
            )
        ].append(bool(row["correct"]))

    lines = ["condition,gap_checkpoint,boundary_offset,n,accuracy,ci95_low,ci95_high"]
    for condition, definition_gap, boundary_offset in sorted(grouped):
        values = grouped[(condition, definition_gap, boundary_offset)]
        accuracy = mean(values)
        low, high = wilson_interval(sum(values), len(values))
        lines.append(
            f"{condition},{definition_gap},{boundary_offset},{len(values)},"
            f"{accuracy:.4f},{low:.4f},{high:.4f}"
        )
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2D marker-definition rolling KV experiment.")
    add_model_options(parser)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=512)
    parser.add_argument("--definition-gaps", default="32,64,128,256,512,768,1024")
    parser.add_argument("--boundary-offsets", default="-32,0,32,64,128,256")
    parser.add_argument("--leading-filler-tokens", type=int, default=128)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4, help="Independent equal-length prompts per batch; 1 selects serial reference")
    parser.add_argument("--matched-trials", action="store_true", help="Reuse marker, answer and candidates across all gap/offset cells")
    parser.add_argument("--control-trials", type=int, help="Predetermined subset per checkpoint/offset for controls; default all trials")
    parser.add_argument("--choices", type=int, default=4)
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dtype", choices=("auto", "float16", "bfloat16", "float32"), default="auto")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--no-cache-position", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


if __name__ == "__main__":
    main()

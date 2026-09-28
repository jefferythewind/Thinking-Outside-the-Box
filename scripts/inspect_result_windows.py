from __future__ import annotations

import argparse
import csv
from collections import defaultdict

from transformers import AutoTokenizer

from totb.dataset import build_trials


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    distances = [int(value) for value in args.distances.split(",")]
    trials = build_trials(
        tokenizer,
        num_trials=args.trials,
        window_size=args.window_size,
        distances=distances,
        filler_variant=args.filler,
        task=args.task,
        seed=args.seed,
    )
    rows = list(csv.DictReader(open(args.results)))
    verify_rows_match(rows, trials)
    summarize_windows(trials, args.window_size)
    print_examples(tokenizer, trials, args.window_size, args.example_distance, args.examples)


def verify_rows_match(rows: list[dict[str, str]], trials) -> None:
    for row in rows:
        trial = trials[int(row["trial"]) - 1]
        if int(row["distance"]) != trial.distance_outside_window:
            raise AssertionError("CSV distance does not match regenerated trial.")
        if int(row["answer_token_id"]) != trial.answer_token_id:
            raise AssertionError("CSV answer token does not match regenerated trial.")
    print("CSV rows match regenerated trials.")


def summarize_windows(trials, window_size: int) -> None:
    summary: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])
    for trial in trials:
        token_ids = list(trial.prompt_token_ids)
        secret_index = trial.secret_token_index
        final_token_index = len(token_ids) - 1
        final_raw_start = len(token_ids) - window_size
        kv_scoring_start = final_token_index - window_size

        final_raw_contains = final_raw_start <= secret_index <= final_token_index
        kv_scoring_contains = kv_scoring_start <= secret_index <= final_token_index - 1

        values = summary[trial.distance_outside_window]
        values[0] += 1
        values[1] += int(final_raw_contains)
        values[2] += int(kv_scoring_contains)

    print("distance,n,final_raw_contains_answer,kv_scoring_cache_contains_answer")
    for distance in sorted(summary):
        print(f"{distance},{','.join(str(value) for value in summary[distance])}")


def print_examples(tokenizer, trials, window_size: int, distance: int, examples: int) -> None:
    if examples <= 0:
        return

    print(f"\nExamples for distance={distance}")
    shown = 0
    for trial in trials:
        if trial.distance_outside_window != distance:
            continue
        token_ids = list(trial.prompt_token_ids)
        final_token_index = len(token_ids) - 1
        final_raw_start = len(token_ids) - window_size
        kv_scoring_start = final_token_index - window_size
        print("-" * 88)
        print(f"answer_text={trial.answer_text!r} answer_id={trial.answer_token_id}")
        print(f"prompt_tokens={len(token_ids)} secret_index={trial.secret_token_index}")
        print(f"final_raw_start={final_raw_start} kv_scoring_start={kv_scoring_start}")
        print(f"answer_in_final_raw={final_raw_start <= trial.secret_token_index <= final_token_index}")
        print(f"answer_in_kv_scoring={kv_scoring_start <= trial.secret_token_index <= final_token_index - 1}")
        print("final_raw_prefix=", repr(tokenizer.decode(token_ids[final_raw_start:final_raw_start + 30])))
        print("kv_scoring_prefix=", repr(tokenizer.decode(token_ids[kv_scoring_start:kv_scoring_start + 30])))
        shown += 1
        if shown >= examples:
            break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect final raw and rolling-KV scoring windows for result CSVs.")
    parser.add_argument("--results", required=True)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, required=True)
    parser.add_argument("--distances", required=True)
    parser.add_argument("--trials", type=int, required=True)
    parser.add_argument("--task", choices=("code", "code_defined", "emotion", "who_happy"), default="code")
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--example-distance", type=int, default=1)
    parser.add_argument("--examples", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    main()

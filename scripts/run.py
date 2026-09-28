from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tqdm import tqdm

from totb.dataset import assert_trial_controls, build_trials
from totb.evaluate import Row, summarize
from totb.model_utils import add_model_options, load_model
from totb.runner import predict, score_full_prompt, score_last_window, score_rolling_kv


def main() -> None:
    args = parse_args()
    tokenizer, model = load_model(args)

    distances = [int(value) for value in args.distances.split(",")]
    trials = build_trials(
        tokenizer,
        num_trials=args.trials,
        window_size=args.window_size,
        distances=distances,
        num_choices=args.choices,
        filler_variant=args.filler,
        task=args.task,
        seed=args.seed,
    )

    rows: list[Row] = []
    raw_rows: list[dict[str, object]] = []

    for index, trial in enumerate(tqdm(trials, desc="trials"), start=1):
        assert_trial_controls(trial, args.window_size)
        conditions = {
            "last_window": score_last_window(
                model,
                trial.prompt_token_ids,
                trial.candidate_token_ids,
                window_size=args.window_size,
            ),
            "rolling_kv": score_rolling_kv(
                model,
                trial.prompt_token_ids,
                trial.candidate_token_ids,
                window_size=args.window_size,
                use_cache_position=not args.no_cache_position,
            ),
        }
        if args.full_prompt or len(trial.prompt_token_ids) <= args.window_size:
            conditions["full_prompt"] = score_full_prompt(
                model,
                trial.prompt_token_ids,
                trial.candidate_token_ids,
            )

        for condition, scores in conditions.items():
            prediction = predict(scores, trial.answer_token_id)
            rows.append(
                Row(
                    condition=condition,
                    distance=trial.distance_outside_window,
                    correct=prediction.correct,
                )
            )
            raw_rows.append(
                {
                    "trial": index,
                    "model": args.model,
                    "window_size": args.window_size,
                    "seed": args.seed,
                    "choices": args.choices,
                    "filler": args.filler,
                    "candidate_token_ids": " ".join(map(str, trial.candidate_token_ids)),
                    "task": args.task,
                    "condition": condition,
                    "distance": trial.distance_outside_window,
                    "answer_token_id": trial.answer_token_id,
                    "predicted_token_id": prediction.predicted_token_id,
                    "correct": int(prediction.correct),
                    "prompt_tokens": len(trial.prompt_token_ids),
                    "secret_token_index": trial.secret_token_index,
                    "answer_text": trial.answer_text.strip(),
                }
            )

    print(summarize(rows))
    if args.output:
        write_csv(Path(args.output), raw_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rolling KV memory experiment.")
    add_model_options(parser)
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=1024)
    parser.add_argument("--distances", default="1,4,8,16,32,64,128,256")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--choices", type=int, default=4)
    parser.add_argument("--task", choices=("code", "code_defined", "emotion", "who_happy"), default="code")
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dtype", choices=("auto", "float16", "bfloat16", "float32"), default="auto")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--no-cache-position", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

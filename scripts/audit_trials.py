from __future__ import annotations

import argparse

from transformers import AutoTokenizer

from totb.dataset import assert_trial_controls, build_trials


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

    for trial in trials:
        assert_trial_controls(trial, args.window_size)
        first_visible_index = len(trial.prompt_token_ids) - args.window_size
        is_visible = trial.secret_token_index >= first_visible_index
        if trial.distance_outside_window > 0 and is_visible:
            raise AssertionError(
                "Secret is directly visible during scoring: "
                f"secret_index={trial.secret_token_index}, "
                f"first_visible_index={first_visible_index}, "
                f"distance={trial.distance_outside_window}"
            )
        if trial.distance_outside_window <= 0 and not is_visible:
            raise AssertionError(
                "Secret should be visible during scoring but is not: "
                f"secret_index={trial.secret_token_index}, "
                f"first_visible_index={first_visible_index}, "
                f"distance={trial.distance_outside_window}"
            )
        if trial.distance_outside_window != first_visible_index - trial.secret_token_index:
            raise AssertionError("Stored distance does not match scoring-time distance.")

    observed = sorted({trial.distance_outside_window for trial in trials})
    print(
        f"audit passed: trials={len(trials)}, window_size={args.window_size}, "
        f"observed_distances={observed}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit generated trials for direct leakage.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=1024)
    parser.add_argument("--distances", default="1,2,3,4")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--task", choices=("code", "code_defined", "emotion", "who_happy"), default="code")
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    main()

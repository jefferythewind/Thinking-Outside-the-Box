from __future__ import annotations

import argparse

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
        num_choices=args.choices,
        filler_variant=args.filler,
        task=args.task,
        seed=args.seed,
    )

    for index, trial in enumerate(sorted(trials, key=lambda item: item.distance_outside_window), start=1):
        first_visible_index = len(trial.prompt_token_ids) - args.window_size
        last_window_token_ids = trial.prompt_token_ids[-args.window_size:]
        secret_visible = trial.secret_token_index >= first_visible_index
        candidate_texts = [
            tokenizer.decode([token_id]).replace("\n", "\\n")
            for token_id in trial.candidate_token_ids
        ]

        print("=" * 88)
        print(f"trial={index}")
        print(f"distance={trial.distance_outside_window}")
        print(f"prompt_tokens={len(trial.prompt_token_ids)}")
        print(f"window_size={args.window_size}")
        print(f"secret_index={trial.secret_token_index}")
        print(f"first_visible_index={first_visible_index}")
        print(f"secret_visible_in_last_window={secret_visible}")
        print(f"answer_token_id={trial.answer_token_id}")
        print(f"answer_text={trial.answer_text!r}")
        print(f"candidate_token_ids={trial.candidate_token_ids}")
        print(f"candidate_texts={candidate_texts}")
        print()
        print("--- full prompt prefix ---")
        print(trial.prompt[: args.full_chars])
        print()
        print("--- last-window decoded prefix ---")
        print(tokenizer.decode(last_window_token_ids[: args.window_preview_tokens]))
        print()
        print("--- last-window decoded suffix ---")
        print(tokenizer.decode(last_window_token_ids[-args.window_preview_tokens :]))
        print()
        print("--- scoring suffix ---")
        print(trial.prompt[-args.tail_chars :])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect generated memory-retrieval trials.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=1024)
    parser.add_argument("--distances", default="-3,-2,-1,0,1,2,3")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--choices", type=int, default=4)
    parser.add_argument("--task", choices=("code", "code_defined", "emotion", "who_happy"), default="code")
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--full-chars", type=int, default=500)
    parser.add_argument("--tail-chars", type=int, default=500)
    parser.add_argument("--window-preview-tokens", type=int, default=40)
    return parser.parse_args()


if __name__ == "__main__":
    main()

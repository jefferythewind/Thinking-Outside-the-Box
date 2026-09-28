from __future__ import annotations

import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from totb.cache_utils import cache_length, retain_newest_cache_positions
from totb.dataset import assert_trial_controls, build_trials
from totb.runner import score_full_prompt, score_rolling_kv


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype="auto",
        device_map=args.device_map,
    )
    model.eval()

    validate_manual_cache_matches_full(model, tokenizer, args.text, args.score_tolerance)
    validate_dataset_controls(tokenizer, args.window_size)
    validate_cache_truncation(model, tokenizer, args.window_size)
    validate_rolling_matches_full_inside_window(model, tokenizer, args.window_size)
    print("validation passed")


@torch.inference_mode()
def validate_manual_cache_matches_full(model, tokenizer, text: str, tolerance: float) -> None:
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    if len(token_ids) < 3:
        raise ValueError("Validation text must contain at least three tokens.")

    full_scores = score_full_prompt(model, token_ids, token_ids[:3])
    cached_scores = score_manual_cached(model, token_ids, token_ids[:3])
    if max(full_scores, key=full_scores.get) != max(cached_scores, key=cached_scores.get):
        raise AssertionError("Full prompt and manual cached scoring disagree inside the window.")
    for token_id in token_ids[:3]:
        difference = abs(full_scores[token_id] - cached_scores[token_id])
        if difference > tolerance:
            raise AssertionError(
                "Full prompt and manual cached scores differ more than tolerance: "
                f"token_id={token_id}, full={full_scores[token_id]:.6f}, "
                f"cached={cached_scores[token_id]:.6f}, difference={difference:.6f}, "
                f"tolerance={tolerance:.6f}"
            )


@torch.inference_mode()
def score_manual_cached(model, token_ids: list[int], candidate_token_ids: list[int]) -> dict[int, float]:
    cache = None
    logits = None
    for position, token_id in enumerate(token_ids):
        input_ids = torch.tensor([[token_id]], dtype=torch.long, device=model.device)
        kwargs = {
            "input_ids": input_ids,
            "past_key_values": cache,
            "use_cache": True,
        }
        if cache is not None:
            kwargs["cache_position"] = torch.tensor([position], dtype=torch.long, device=model.device)
        outputs = model(**kwargs)
        cache = outputs.past_key_values
        logits = outputs.logits[0, -1]

    assert logits is not None
    log_probs = torch.log_softmax(logits[candidate_token_ids], dim=0)
    return {
        token_id: float(log_prob.detach().cpu())
        for token_id, log_prob in zip(candidate_token_ids, log_probs, strict=True)
    }


def validate_dataset_controls(tokenizer, window_size: int) -> None:
    trials = build_trials(
        tokenizer,
        num_trials=2,
        window_size=window_size,
        distances=(1, 4),
        seed=123,
    )
    for trial in trials:
        assert_trial_controls(trial, window_size)

    code_defined_trials = build_trials(
        tokenizer,
        num_trials=1,
        window_size=window_size,
        distances=(-1, 1),
        task="code_defined",
        seed=123,
    )
    for trial in code_defined_trials:
        assert_trial_controls(trial, window_size)

    emotion_trials = build_trials(
        tokenizer,
        num_trials=1,
        window_size=window_size,
        distances=(-1, 1),
        task="emotion",
        seed=123,
    )
    for trial in emotion_trials:
        assert_trial_controls(trial, window_size)

    who_happy_trials = build_trials(
        tokenizer,
        num_trials=1,
        window_size=window_size,
        distances=(2,),
        task="who_happy",
        seed=123,
    )
    for trial in who_happy_trials:
        assert_trial_controls(trial, window_size)


@torch.inference_mode()
def validate_cache_truncation(model, tokenizer, window_size: int) -> None:
    text = "Cache truncation validation. " * max(8, window_size // 4)
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    input_ids = torch.tensor([token_ids], dtype=torch.long, device=model.device)
    outputs = model(input_ids=input_ids, use_cache=True)
    cache = retain_newest_cache_positions(outputs.past_key_values, window_size)
    if cache_length(cache) > window_size:
        raise AssertionError("Cache truncation failed.")


@torch.inference_mode()
def validate_rolling_matches_full_inside_window(model, tokenizer, window_size: int) -> None:
    text = "The code is BLUE.\n\nQuestion: what is the code?\n\nAnswer:"
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    candidate_ids = token_ids[: min(4, len(token_ids))]
    full_scores = score_full_prompt(model, token_ids, candidate_ids)
    rolling_scores = score_rolling_kv(
        model,
        token_ids,
        candidate_ids,
        window_size=max(window_size, len(token_ids)),
    )
    for token_id in candidate_ids:
        if abs(full_scores[token_id] - rolling_scores[token_id]) > 1e-5:
            raise AssertionError("Rolling scoring differs from full scoring inside the window.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate rolling KV experiment plumbing.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--device-map", default="auto")
    parser.add_argument(
        "--score-tolerance",
        type=float,
        default=0.5,
        help=(
            "Allowed forced-choice log-probability drift between full-prompt "
            "and token-by-token cached inference. Low-precision kernels are "
            "not bit-exact across these paths."
        ),
    )
    parser.add_argument(
        "--text",
        default="Manual cached inference should match ordinary prompt inference.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()

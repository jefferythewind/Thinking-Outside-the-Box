from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import torch
from transformers import DynamicCache

from totb.cache_utils import (
    cache_length,
    retain_newest_cache_positions,
    tensorize_position,
    tensorize_token,
    validate_cache_window,
)


@dataclass(frozen=True)
class Prediction:
    predicted_token_id: int
    answer_token_id: int
    correct: bool
    scores: dict[int, float]


@torch.inference_mode()
def score_full_prompt(model, token_ids: Iterable[int], candidate_token_ids: Iterable[int]) -> dict[int, float]:
    device = model.device
    input_ids = torch.tensor([list(token_ids)], dtype=torch.long, device=device)
    outputs = model(input_ids=input_ids, use_cache=False)
    logits = outputs.logits[0, -1]
    return _scores_from_logits(logits, candidate_token_ids)


@torch.inference_mode()
def score_last_window(
    model,
    token_ids: Iterable[int],
    candidate_token_ids: Iterable[int],
    *,
    window_size: int,
) -> dict[int, float]:
    return score_full_prompt(model, list(token_ids)[-window_size:], candidate_token_ids)


@torch.inference_mode()
def score_rolling_kv(
    model,
    token_ids: Iterable[int],
    candidate_token_ids: Iterable[int],
    *,
    window_size: int,
    use_cache_position: bool = True,
) -> dict[int, float]:
    token_list = list(token_ids)
    if len(token_list) <= window_size:
        return score_full_prompt(model, token_list, candidate_token_ids)

    device = model.device
    prefill_ids = torch.tensor([token_list[:window_size]], dtype=torch.long, device=device)
    outputs = model(input_ids=prefill_ids, past_key_values=DynamicCache(), use_cache=True)
    cache = retain_newest_cache_positions(outputs.past_key_values, window_size)
    validate_cache_window(cache, window_size)

    logits = outputs.logits[0, -1]
    for absolute_position, token_id in enumerate(token_list[window_size:], start=window_size):
        kwargs = {
            "input_ids": tensorize_token(token_id, device),
            "past_key_values": cache,
            "use_cache": True,
        }
        if use_cache_position:
            kwargs["cache_position"] = tensorize_position(absolute_position, device)
            kwargs["position_ids"] = tensorize_position(absolute_position, device).unsqueeze(0)

        outputs = model(**kwargs)
        cache = retain_newest_cache_positions(outputs.past_key_values, window_size)
        validate_cache_window(cache, window_size)
        logits = outputs.logits[0, -1]

    return _scores_from_logits(logits, candidate_token_ids)


def predict(scores: dict[int, float], answer_token_id: int) -> Prediction:
    predicted_token_id = max(scores, key=scores.get)
    return Prediction(
        predicted_token_id=predicted_token_id,
        answer_token_id=answer_token_id,
        correct=predicted_token_id == answer_token_id,
        scores=scores,
    )


def _scores_from_logits(logits: torch.Tensor, candidate_token_ids: Iterable[int]) -> dict[int, float]:
    token_ids = list(candidate_token_ids)
    log_probs = torch.log_softmax(logits[token_ids], dim=0)
    return {
        token_id: float(log_prob.detach().cpu())
        for token_id, log_prob in zip(token_ids, log_probs, strict=True)
    }

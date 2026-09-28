from __future__ import annotations

import torch
from transformers import DynamicCache

from totb.cache_utils import retain_newest_cache_positions, validate_cache_window
from totb.runner import _scores_from_logits


@torch.inference_mode()
def score_rolling_kv_batched(model, prompts, candidate_lists, *, window_size):
    if not prompts or len(prompts) != len(candidate_lists):
        raise ValueError("Provide one candidate list per prompt")
    lengths = {len(prompt) for prompt in prompts}
    if len(lengths) != 1 or min(lengths) == 0 or window_size < 1:
        raise ValueError("Batch requires nonempty, equal-length prompts and a positive window")
    tokens = torch.tensor(prompts, dtype=torch.long, device=model.device)
    length = tokens.shape[1]
    if length <= window_size:
        outputs = model(input_ids=tokens, use_cache=False)
    else:
        outputs = model(input_ids=tokens[:, :window_size], past_key_values=DynamicCache(), use_cache=True)
        cache = retain_newest_cache_positions(outputs.past_key_values, window_size)
        validate_cache_window(cache, window_size)
        for position in range(window_size, length):
            absolute = torch.tensor([position], dtype=torch.long, device=model.device)
            outputs = model(input_ids=tokens[:, position:position + 1], past_key_values=cache,
                            cache_position=absolute, position_ids=absolute[None, :], use_cache=True)
            cache = retain_newest_cache_positions(outputs.past_key_values, window_size)
            validate_cache_window(cache, window_size)
    return [_scores_from_logits(outputs.logits[index, -1], candidates)
            for index, candidates in enumerate(candidate_lists)]

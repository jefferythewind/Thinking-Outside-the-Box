from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Sequence

from totb.dataset import FILLER_VARIANTS, collect_single_token_candidates, sample_safe_choices


@dataclass(frozen=True)
class MarkerTrial:
    prompt: str
    answer_token_id: int
    candidate_token_ids: tuple[int, ...]
    answer_text: str
    prompt_token_ids: tuple[int, ...]
    answer_token_index: int
    preamble_end_index: int
    carrier_block_start_index: int
    carrier_start_index: int
    definition_gap: int
    target_carrier_gap: int
    boundary_offset: int
    marker_text: str
    carrier_rows: tuple[str, ...]
    gap_checkpoint: str = ""
    matched_pair_id: int | None = None


MARKER_TEXTS = (
    "<K7>",
    "<P2>",
    "<M8>",
    "<R4>",
    "<Z9>",
    "<Q3>",
    "<N5>",
    "<V6>",
)

SUFFIX = "\n\nQuestion:\nWhat is the secret code?\n\nAnswer:"
BOUNDARY_OFFSETS = "-128,-64,-32,-16,-8,-4,-2,-1,0,1,2,4,8,16,32,64,128"


def build_marker_trials(
    tokenizer,
    *,
    num_trials: int,
    window_size: int,
    definition_gaps: Sequence[int | str],
    boundary_offsets: Sequence[int],
    num_choices: int = 4,
    filler_variant: str = "neutral",
    seed: int = 0,
    leading_filler_tokens: int = 128,
    matched_trials: bool = False,
) -> list[MarkerTrial]:
    rng = random.Random(seed)
    candidate_pool = collect_single_token_candidates(tokenizer)
    trials: list[MarkerTrial] = []
    initial_rng_state = rng.getstate()

    for definition_gap in definition_gaps:
        for boundary_offset in boundary_offsets:
            if matched_trials:
                rng.setstate(initial_rng_state)
            for pair_index in range(num_trials):
                marker_text = rng.choice(MARKER_TEXTS)
                choices = sample_safe_choices(
                    tokenizer,
                    rng,
                    candidate_pool,
                    num_choices=num_choices,
                    filler_variant=filler_variant,
                    task="code",
                )
                answer_token_id, answer_text = rng.choice(choices)
                prefix_length = len(tokenizer.encode(f"\n{marker_text}:", add_special_tokens=False))
                boundary_gap = window_size - prefix_length
                checkpoint = str(definition_gap)
                actual_gap = {"B-1": boundary_gap - 1, "B": boundary_gap, "B+1": boundary_gap + 1}.get(checkpoint)
                if actual_gap is None:
                    actual_gap = int(definition_gap)
                trials.append(
                    replace(build_marker_prompt(
                        tokenizer,
                        answer_token_id=answer_token_id,
                        answer_text=answer_text,
                        candidate_token_ids=tuple(token_id for token_id, _ in choices),
                        marker_text=marker_text,
                        definition_gap=actual_gap,
                        boundary_offset=boundary_offset,
                        window_size=window_size,
                        filler_variant=filler_variant,
                        leading_filler_tokens=leading_filler_tokens,
                    ), gap_checkpoint=checkpoint,
                        matched_pair_id=pair_index + 1 if matched_trials else None)
                )

    rng.shuffle(trials)
    return trials


def build_marker_prompt(
    tokenizer,
    *,
    answer_token_id: int,
    answer_text: str,
    candidate_token_ids: tuple[int, ...],
    marker_text: str,
    definition_gap: int,
    boundary_offset: int,
    window_size: int,
    filler_variant: str,
    leading_filler_tokens: int = 128,
) -> MarkerTrial:
    if window_size <= 0 or leading_filler_tokens < 0:
        raise ValueError("Window must be positive and leading filler non-negative.")
    if definition_gap < 0:
        raise ValueError("definition_gap must be non-negative.")
    if filler_variant not in FILLER_VARIANTS:
        raise ValueError(f"Unknown filler variant: {filler_variant}")
    if tokenizer.encode(answer_text, add_special_tokens=False) != [answer_token_id]:
        raise ValueError(f"Answer text is not stable as one token: {answer_text!r}")

    preamble = (
        "This is a memory test.\n\n"
        "The secret code will appear later in this text.\n"
        f"The secret is the value immediately following {marker_text}.\n"
    )
    carrier_row = f"\n{marker_text}:{answer_text}"

    preamble_ids = [*repeat_to_length(tokenizer.encode(FILLER_VARIANTS[filler_variant], add_special_tokens=False), leading_filler_tokens), *tokenizer.encode(preamble, add_special_tokens=False)]
    marker_gap_ids = repeat_to_length(
        tokenizer.encode(FILLER_VARIANTS[filler_variant], add_special_tokens=False),
        definition_gap,
    )
    carrier_prefix_ids = tokenizer.encode(f"\n{marker_text}:", add_special_tokens=False)
    carrier_row_ids = [*carrier_prefix_ids, answer_token_id]
    suffix_ids = tokenizer.encode(SUFFIX, add_special_tokens=False)
    tail_filler_ids = tokenizer.encode(FILLER_VARIANTS[filler_variant], add_special_tokens=False)

    preamble_end_index = len(preamble_ids)
    carrier_block_start_index = preamble_end_index + len(marker_gap_ids)
    carrier_start_index = carrier_block_start_index
    answer_token_index = carrier_start_index + len(carrier_prefix_ids)
    target_carrier_gap = definition_gap
    target_final_raw_start = answer_token_index + boundary_offset
    if target_final_raw_start < 0:
        raise ValueError("Offset precedes prompt start; increase leading_filler_tokens.")

    token_ids = [
        *preamble_ids,
        *marker_gap_ids,
        *carrier_row_ids,
    ]
    tail_index = 0
    while True:
        candidate_token_ids_full = [*token_ids, *suffix_ids]
        final_raw_start = len(candidate_token_ids_full) - window_size
        if final_raw_start >= target_final_raw_start:
            if final_raw_start != target_final_raw_start:
                raise ValueError(
                    "Could not hit exact boundary offset with current tokenizer/filler: "
                    f"target={target_final_raw_start}, actual={final_raw_start}"
                )
            prompt = tokenizer.decode(candidate_token_ids_full)
            if candidate_token_ids_full[answer_token_index] != answer_token_id:
                raise AssertionError("Answer index does not identify the secret token.")
            if candidate_token_ids_full.count(answer_token_id) != 1:
                raise AssertionError("Secret token must occur exactly once in the prompt.")
            return MarkerTrial(
                prompt=prompt,
                answer_token_id=answer_token_id,
                candidate_token_ids=candidate_token_ids,
                answer_text=answer_text,
                prompt_token_ids=tuple(candidate_token_ids_full),
                answer_token_index=answer_token_index,
                preamble_end_index=preamble_end_index,
                carrier_block_start_index=carrier_block_start_index,
                carrier_start_index=carrier_start_index,
                definition_gap=definition_gap,
                target_carrier_gap=target_carrier_gap,
                boundary_offset=boundary_offset,
                marker_text=marker_text,
                carrier_rows=(carrier_row,),
            )
        token_ids.append(tail_filler_ids[tail_index % len(tail_filler_ids)])
        tail_index += 1


def repeat_to_length(token_ids: Sequence[int], length: int) -> list[int]:
    if length == 0:
        return []
    if not token_ids:
        raise ValueError("Cannot repeat empty token list.")
    return [token_ids[index % len(token_ids)] for index in range(length)]

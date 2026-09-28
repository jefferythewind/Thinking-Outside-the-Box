from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Trial:
    prompt: str
    answer_token_id: int
    candidate_token_ids: tuple[int, ...]
    answer_text: str
    prompt_token_ids: tuple[int, ...]
    secret_token_index: int
    distance_outside_window: int


FILLER_VARIANTS = {
    "neutral": (
        " The document contains ordinary background notes about trees, roads,"
        " weather, tools, books, chairs, lamps, windows, and quiet rooms."
    ),
    "repeated": " The note says this sentence is filler and carries no useful information.",
    "distractor": (
        " A different fake code is mentioned elsewhere, but it is not the answer."
        " Ignore unrelated labels and continue reading the passage."
    ),
    "breadcrumb": (
        " Remember the code from earlier. The passage continues with unrelated"
        " details while preserving the earlier code for the final question."
    ),
}

TASK_TEMPLATES = {
    "code": {
        "prefix": "This is a memory test.\n\nThe secret code is:",
        "answer_suffix": "",
        "suffix": "\n\nQuestion:\nWhat is the secret code?\n\nAnswer:",
    },
    "code_defined": {
        "prefix": (
            "This is a memory test.\n\n"
            "The secret code is defined by the following identifier:"
        ),
        "answer_suffix": "",
        "suffix": "\n\nQuestion:\nWhat is the secret code?\n\nAnswer:",
    },
    "emotion": {
        "prefix": "This is a memory test.\n\nSarah is",
        "answer_suffix": "",
        "suffix": "\n\nQuestion:\nHow does Sarah feel?\n\nSarah is",
    },
    "who_happy": {
        "prefix": "This is a memory test.\n\n",
        "answer_suffix": " is happy",
        "suffix": "\n\nQuestion:\nWho is happy?\n\nAnswer:",
    },
}

EMOTION_CHOICES = (" happy", " sad", " angry", " tired")
PERSON_CHOICES = ("Sarah", "John", "Alice", "Mark")


def build_trials(
    tokenizer,
    *,
    num_trials: int,
    window_size: int,
    distances: Sequence[int],
    num_choices: int = 4,
    filler_variant: str = "neutral",
    task: str = "code",
    seed: int = 0,
) -> list[Trial]:
    rng = random.Random(seed)
    candidate_pool = collect_task_candidates(tokenizer, task)
    if len(candidate_pool) < num_choices:
        raise ValueError("Not enough single-token candidate labels found.")

    trials: list[Trial] = []
    for distance in distances:
        for _ in range(num_trials):
            choices = sample_safe_choices(
                tokenizer,
                rng,
                candidate_pool,
                num_choices=num_choices,
                filler_variant=filler_variant,
                task=task,
            )
            answer_token_id, answer_text = rng.choice(choices)
            prompt, token_ids, secret_index, actual_distance = build_prompt_at_distance(
                tokenizer,
                answer_token_id=answer_token_id,
                answer_text=answer_text,
                window_size=window_size,
                target_distance=distance,
                filler_variant=filler_variant,
                task=task,
            )
            trials.append(
                Trial(
                    prompt=prompt,
                    answer_token_id=answer_token_id,
                    candidate_token_ids=tuple(token_id for token_id, _ in choices),
                    answer_text=answer_text,
                    prompt_token_ids=tuple(token_ids),
                    secret_token_index=secret_index,
                    distance_outside_window=actual_distance,
                )
            )

    rng.shuffle(trials)
    return trials


def collect_task_candidates(tokenizer, task: str) -> list[tuple[int, str]]:
    if task in ("code", "code_defined"):
        return collect_single_token_candidates(tokenizer)
    if task == "emotion":
        candidates = []
        for text in EMOTION_CHOICES:
            token_ids = tokenizer.encode(text, add_special_tokens=False)
            if len(token_ids) != 1:
                raise ValueError(f"Emotion choice is not one token: {text!r} -> {token_ids}")
            candidates.append((token_ids[0], text))
        return candidates
    if task == "who_happy":
        candidates = []
        for text in PERSON_CHOICES:
            token_ids = tokenizer.encode(text, add_special_tokens=False)
            if len(token_ids) != 1:
                raise ValueError(f"Person choice is not one token: {text!r} -> {token_ids}")
            candidates.append((token_ids[0], text))
        return candidates
    raise ValueError(f"Unknown task: {task}")


def collect_single_token_candidates(tokenizer, *, max_candidates: int = 512) -> list[tuple[int, str]]:
    candidates: list[tuple[int, str]] = []
    vocab_size = len(tokenizer)
    special_ids = set(getattr(tokenizer, "all_special_ids", []) or [])

    for token_id in range(vocab_size):
        if token_id in special_ids:
            continue
        text = tokenizer.decode([token_id])
        stripped = text.strip()
        if not _looks_like_label(stripped):
            continue
        encoded = tokenizer.encode(text, add_special_tokens=False)
        if encoded == [token_id]:
            candidates.append((token_id, text))
        if len(candidates) >= max_candidates:
            break

    return candidates


def sample_safe_choices(
    tokenizer,
    rng: random.Random,
    candidate_pool: Sequence[tuple[int, str]],
    *,
    num_choices: int,
    filler_variant: str,
    task: str,
) -> tuple[tuple[int, str], ...]:
    template = TASK_TEMPLATES[task]
    static_text = template["prefix"] + template["answer_suffix"] + FILLER_VARIANTS[filler_variant] + template["suffix"]
    static_token_ids = set(tokenizer.encode(static_text, add_special_tokens=False))
    safe_pool = [candidate for candidate in candidate_pool if candidate[0] not in static_token_ids]
    if len(safe_pool) < num_choices:
        raise ValueError("Not enough safe candidate labels found.")
    return tuple(rng.sample(safe_pool, num_choices))


def build_prompt_at_distance(
    tokenizer,
    *,
    answer_token_id: int,
    answer_text: str,
    window_size: int,
    target_distance: int,
    filler_variant: str,
    task: str = "code",
) -> tuple[str, list[int], int, int]:
    if filler_variant not in FILLER_VARIANTS:
        raise ValueError(f"Unknown filler variant: {filler_variant}")
    if task not in TASK_TEMPLATES:
        raise ValueError(f"Unknown task: {task}")

    prefix = TASK_TEMPLATES[task]["prefix"]
    answer_suffix = TASK_TEMPLATES[task]["answer_suffix"]
    suffix = TASK_TEMPLATES[task]["suffix"]
    filler_unit = FILLER_VARIANTS[filler_variant]

    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    answer_suffix_ids = tokenizer.encode(answer_suffix, add_special_tokens=False)
    suffix_ids = tokenizer.encode(suffix, add_special_tokens=False)
    filler_ids = tokenizer.encode(filler_unit, add_special_tokens=False)

    if tokenizer.encode(answer_text, add_special_tokens=False) != [answer_token_id]:
        raise ValueError(f"Answer text is not stable as one token: {answer_text!r}")

    token_ids = [*prefix_ids, answer_token_id, *answer_suffix_ids]
    secret_index = len(prefix_ids)
    filler_index = 0

    while True:
        candidate_token_ids = [*token_ids, *suffix_ids]
        first_visible_index_during_scoring = len(candidate_token_ids) - window_size
        distance = first_visible_index_during_scoring - secret_index
        if distance >= target_distance and _visibility_matches_target(
            distance,
            target_distance,
            secret_index,
            first_visible_index_during_scoring,
        ):
            prompt = tokenizer.decode(candidate_token_ids)
            return prompt, candidate_token_ids, secret_index, distance
        token_ids.append(filler_ids[filler_index % len(filler_ids)])
        filler_index += 1


def assert_trial_controls(trial: Trial, window_size: int) -> None:
    last_window = trial.prompt_token_ids[-window_size:]
    if trial.distance_outside_window > 0 and trial.answer_token_id in last_window:
        raise AssertionError("Secret answer token appears in the last-window control.")
    if trial.distance_outside_window <= 0 and trial.answer_token_id not in last_window:
        raise AssertionError("Secret answer token is missing from the visible-window control.")


def _visibility_matches_target(
    distance: int,
    target_distance: int,
    secret_index: int,
    first_visible_index: int,
) -> bool:
    if distance != target_distance:
        return False
    if target_distance > 0:
        return secret_index < first_visible_index
    return secret_index >= first_visible_index


def _find_secret_index(token_ids: Sequence[int], secret_token_id: int) -> int:
    matches = [index for index, token_id in enumerate(token_ids) if token_id == secret_token_id]
    if len(matches) != 1:
        raise ValueError(
            f"Expected the secret token to appear exactly once, found {len(matches)} occurrences."
        )
    return matches[0]


def _looks_like_label(text: str) -> bool:
    return 2 <= len(text) <= 8 and text.isascii() and text.isalpha() and text.isupper()

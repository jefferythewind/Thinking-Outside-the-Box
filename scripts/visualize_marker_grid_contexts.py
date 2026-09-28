from __future__ import annotations

import argparse
from pathlib import Path

from transformers import AutoTokenizer

from totb.marker_dataset import BOUNDARY_OFFSETS, build_marker_trials


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    definition_gaps = [int(value) for value in args.definition_gaps.split(",")]
    boundary_offsets = [int(value) for value in args.boundary_offsets.split(",")]
    trials = build_marker_trials(
        tokenizer,
        num_trials=1,
        window_size=args.window_size,
        definition_gaps=definition_gaps,
        boundary_offsets=boundary_offsets,
        num_choices=args.choices,
        filler_variant=args.filler,
        seed=args.seed,
        leading_filler_tokens=args.leading_filler_tokens,
    )
    trials.sort(key=lambda trial: (trial.definition_gap, trial.boundary_offset))
    write_markdown(
        trials,
        tokenizer=tokenizer,
        window_size=args.window_size,
        output=Path(args.output),
        preview_tokens=args.preview_tokens,
    )


def write_markdown(trials, *, tokenizer, window_size: int, output: Path, preview_tokens: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Marker Definition Grid Context Examples",
        "",
        "This document shows concrete inputs for the marker-definition grid experiment.",
        "",
        "The prompt has three relevant parts:",
        "",
        "1. A defining preamble says which marker names the secret.",
        "2. A visible carrier row gives that marker an arbitrary code value.",
        "3. A final question asks for the secret code.",
        "",
        "Offsets are anchored to the answer token: offset = final raw start - answer index. "
        "At zero the code is the first raw token; at +1 it is absent from raw input but still in the cache used for the final scoring step; at +2 it is absent from both. "
        "Leading filler makes the negative offsets feasible. These are generated examples, not rows reconstructed from a results CSV.",
        "",
        f"- Window size: `{window_size}`",
        "",
        "| definition_gap | boundary_offset | raw has definition | raw has carrier start | raw has answer | target carrier gap | marker | answer | final raw window starts with | carrier row |",
        "|---:|---:|:---:|:---:|:---:|---:|---|---|---|---|",
    ]
    for trial in trials:
        final_raw_start = len(trial.prompt_token_ids) - window_size
        raw_has_definition = final_raw_start < trial.preamble_end_index
        raw_has_target_row = final_raw_start <= trial.carrier_start_index <= len(trial.prompt_token_ids) - 1
        raw_has_answer = final_raw_start <= trial.answer_token_index <= len(trial.prompt_token_ids) - 1
        snippet = tokenizer.decode(trial.prompt_token_ids[final_raw_start : final_raw_start + preview_tokens])
        lines.append(
            "| "
            f"{trial.definition_gap} | "
            f"{trial.boundary_offset} | "
            f"{yes_no(raw_has_definition)} | "
            f"{yes_no(raw_has_target_row)} | "
            f"{yes_no(raw_has_answer)} | "
            f"{trial.target_carrier_gap} | "
            f"`{escape_cell(trial.marker_text)}` | "
            f"`{escape_cell(trial.answer_text.strip())}` | "
            f"`{escape_cell(snippet)}` | "
            f"`{escape_cell(' / '.join(row.strip() for row in trial.carrier_rows))}` |"
        )

    for trial in trials:
        raw_start = len(trial.prompt_token_ids) - window_size
        lines.extend([
            "", f"## Gap {trial.definition_gap}, offset {trial.boundary_offset}", "",
            f"Expected answer: `{trial.answer_text}`. Answer index: {trial.answer_token_index}; raw start: {raw_start}; scoring cache start: {max(0, raw_start - 1)}.",
            "", "### Full prompt", "", "```text", trial.prompt, "```",
            "", "### Final raw window", "", "```text",
            tokenizer.decode(trial.prompt_token_ids[-window_size:]), "```",
        ])
    output.write_text("\n".join(lines) + "\n")
    print(f"wrote {output}")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def escape_cell(value: str) -> str:
    return value.replace("\n", "\\n").replace("|", "\\|")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write marker-grid context examples to Markdown.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=512)
    parser.add_argument("--definition-gaps", default="0,4,8,16,32,64,128")
    parser.add_argument("--boundary-offsets", default=BOUNDARY_OFFSETS)
    parser.add_argument("--leading-filler-tokens", type=int, default=128)
    parser.add_argument("--choices", type=int, default=4)
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--preview-tokens", type=int, default=32)
    parser.add_argument("--output", default="runs/marker_grid_context_examples.md")
    return parser.parse_args()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from transformers import AutoTokenizer

from totb.dataset import build_prompt_at_distance, collect_task_candidates


def main() -> None:
    args = parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    distances = [int(value) for value in args.distances.split(",")]
    answer_token_id, answer_text = pick_answer_token(tokenizer, args.answer, args.task)

    examples = []
    for distance in distances:
        prompt, token_ids, secret_index, actual_distance = build_prompt_at_distance(
            tokenizer,
            answer_token_id=answer_token_id,
            answer_text=answer_text,
            window_size=args.window_size,
            target_distance=distance,
            filler_variant=args.filler,
            task=args.task,
        )
        examples.append(
            {
                "distance": actual_distance,
                "prompt": prompt,
                "token_ids": token_ids,
                "secret_index": secret_index,
                "final_raw_start": len(token_ids) - args.window_size,
                "kv_scoring_start": len(token_ids) - 1 - args.window_size,
            }
        )

    plot_context_windows(examples, args.window_size, answer_text, args.task, Path(args.output))
    if args.markdown:
        write_markdown(examples, tokenizer, args.window_size, answer_text, args.task, Path(args.markdown), args.preview_tokens)


def pick_answer_token(tokenizer, requested_answer: str | None, task: str) -> tuple[int, str]:
    if requested_answer:
        token_ids = tokenizer.encode(requested_answer, add_special_tokens=False)
        if len(token_ids) != 1:
            raise ValueError(f"Requested answer must encode to one token: {requested_answer!r}")
        return token_ids[0], requested_answer

    candidates = collect_task_candidates(tokenizer, task)
    if not candidates:
        raise ValueError("No single-token answer candidates found.")
    return candidates[0]


def plot_context_windows(examples: list[dict], window_size: int, answer_text: str, task: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(12, 0.55 * len(examples) + 2.2))

    for row, example in enumerate(examples):
        token_count = len(example["token_ids"])
        final_raw_start = example["final_raw_start"]
        kv_scoring_start = example["kv_scoring_start"]
        secret_index = example["secret_index"]

        axis.broken_barh([(0, token_count)], (row - 0.32, 0.64), facecolors="#dddddd", edgecolors="none")
        axis.broken_barh(
            [(final_raw_start, token_count - final_raw_start)],
            (row - 0.32, 0.64),
            facecolors="#9ecae1",
            edgecolors="none",
        )
        axis.broken_barh(
            [(kv_scoring_start, token_count - 1 - kv_scoring_start)],
            (row - 0.18, 0.36),
            facecolors="#fdae6b",
            alpha=0.85,
            edgecolors="none",
        )
        axis.scatter([secret_index], [row], color="#d62728", s=45, zorder=4)
        axis.text(token_count + 2, row, f"d={example['distance']}", va="center", fontsize=9)

    axis.axvline(examples[0]["secret_index"], color="#d62728", linewidth=1.2, alpha=0.8)
    axis.set_title(f"Context Window Shift Example: {task} token {answer_text!r}, W={window_size}")
    axis.set_xlabel("Token position in full prompt")
    axis.set_yticks(range(len(examples)))
    axis.set_yticklabels([str(example["distance"]) for example in examples])
    axis.set_ylabel("Distance")
    axis.set_ylim(-0.8, len(examples) - 0.2)
    axis.grid(axis="x", alpha=0.2)

    legend_items = [
        plt.Rectangle((0, 0), 1, 1, color="#dddddd", label="Full prompt"),
        plt.Rectangle((0, 0), 1, 1, color="#9ecae1", label="Final raw last window"),
        plt.Rectangle((0, 0), 1, 1, color="#fdae6b", label="Rolling-KV scoring cache"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#d62728", markersize=7, label="Answer token"),
    ]
    axis.legend(handles=legend_items, loc="upper left", bbox_to_anchor=(0, 1.02), ncols=4, frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    print(f"wrote {output}")


def write_markdown(
    examples: list[dict],
    tokenizer,
    window_size: int,
    answer_text: str,
    task: str,
    output: Path,
    preview_tokens: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Context Window Distance Example",
        "",
        f"- Task: `{task}`",
        f"- Window size: `{window_size}`",
        f"- Answer token: `{answer_text.strip()}`",
        "",
        "| distance | final raw contains answer | KV scoring cache contains answer | final raw window starts with |",
        "|---:|:---:|:---:|---|",
    ]
    for example in examples:
        token_ids = example["token_ids"]
        final_raw_start = example["final_raw_start"]
        kv_scoring_start = example["kv_scoring_start"]
        secret_index = example["secret_index"]
        final_raw_contains = final_raw_start <= secret_index <= len(token_ids) - 1
        kv_contains = kv_scoring_start <= secret_index <= len(token_ids) - 2
        snippet = tokenizer.decode(token_ids[final_raw_start : final_raw_start + preview_tokens])
        snippet = snippet.replace("\n", "\\n").replace("|", "\\|")
        lines.append(
            f"| {example['distance']} | {yes_no(final_raw_contains)} | {yes_no(kv_contains)} | `{snippet}` |"
        )
    output.write_text("\n".join(lines) + "\n")
    print(f"wrote {output}")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize how distance shifts the secret around the context window.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    parser.add_argument("--window-size", type=int, default=128)
    parser.add_argument("--distances", default="-5,-4,-3,-2,-1,0,1,2,3,4,5")
    parser.add_argument("--task", choices=("code", "code_defined", "emotion", "who_happy"), default="code")
    parser.add_argument("--filler", choices=("neutral", "repeated", "distractor", "breadcrumb"), default="neutral")
    parser.add_argument("--answer")
    parser.add_argument("--output", default="runs/context_window_distance_example.png")
    parser.add_argument("--markdown", default="runs/context_window_distance_example.md")
    parser.add_argument("--preview-tokens", type=int, default=24)
    return parser.parse_args()


if __name__ == "__main__":
    main()

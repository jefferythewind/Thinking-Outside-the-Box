from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt


def main() -> None:
    args = parse_args()
    with open(args.input, newline="") as handle:
        rows = list(csv.DictReader(handle))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plot_heatmaps(rows, output, args.title)
    print(f"wrote {output}")


def plot_heatmaps(rows: list[dict[str, str]], output: Path, title: str) -> None:
    grouped: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                row["condition"],
                row.get("gap_checkpoint") or row["definition_gap"],
                int(row["boundary_offset"]),
            )
        ].append(int(row["correct"]))

    conditions = [condition for condition in ("last_window", "full_prompt", "rolling_kv") if any(key[0] == condition for key in grouped)]
    boundary_order = {"B-1": 511, "B": 512, "B+1": 513}
    gaps = sorted({key[1] for key in grouped}, key=lambda gap: boundary_order[gap] if gap in boundary_order else int(gap))
    offsets = sorted({key[2] for key in grouped})

    fig, axes = plt.subplots(1, len(conditions), figsize=(6.5 * len(conditions), 8), sharey=True, layout="constrained")
    if len(conditions) == 1:
        axes = [axes]

    image = None
    for axis, condition in zip(axes, conditions, strict=True):
        matrix = []
        for offset in offsets:
            row_values = []
            for gap in gaps:
                values = grouped.get((condition, gap, offset), [])
                row_values.append(sum(values) / len(values) if values else float("nan"))
            matrix.append(row_values)

        image = axis.imshow(matrix, vmin=0.0, vmax=1.0, origin="lower", aspect="auto", cmap="viridis")
        axis.set_title(label_for(condition))
        axis.set_xlabel("Definition → carrier gap (tokens)")
        axis.set_xticks(range(len(gaps)))
        axis.set_xticklabels(gaps, rotation=45)
        axis.set_yticks(range(len(offsets)))
        axis.set_yticklabels(offsets)
        if 0 in offsets:
            axis.axhline(offsets.index(0), color="white", linewidth=0.8, alpha=0.7)
        for y, offset in enumerate(offsets):
            for x, gap in enumerate(gaps):
                value = matrix[y][x]
                if value == value:
                    axis.text(x, y, f"{value:.2f}", ha="center", va="center", color=text_color(value), fontsize=8)

    anchors = {row.get("offset_anchor", "preamble_end") for row in rows}
    if len(anchors) != 1:
        raise ValueError("Cannot mix offset anchors in one heatmap.")
    axes[0].set_ylabel("Boundary offset from code (tokens)" if anchors == {"answer_token"} else "Boundary offset from preamble end (tokens)")
    fig.suptitle(title)
    if image is not None:
        fig.colorbar(image, ax=axes, label="Accuracy", fraction=0.046, pad=0.04)
    fig.savefig(output, dpi=180)


def label_for(condition: str) -> str:
    return {
        "last_window": "Last Window Only",
        "full_prompt": "Full Prompt",
        "rolling_kv": "Rolling KV",
    }.get(condition, condition)


def text_color(value: float) -> str:
    return "black" if value > 0.62 else "white"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot marker-definition 2D accuracy heatmaps.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="Marker Definition Grid")
    return parser.parse_args()


if __name__ == "__main__":
    main()

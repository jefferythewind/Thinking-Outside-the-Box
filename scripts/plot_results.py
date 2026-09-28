from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt

from totb.evaluate import wilson_interval


def main() -> None:
    args = parse_args()
    points = load_points(Path(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plot_accuracy(points, output, title=args.title)
    print(f"wrote {output}")


def load_points(path: Path) -> dict[str, list[tuple[int, float, float, float]]]:
    grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
    models = set()
    with path.open() as handle:
        for row in csv.DictReader(handle):
            models.add(row.get("model", "legacy"))
            grouped[(row["condition"], int(row["distance"]))].append(int(row["correct"]))
    if len(models) > 1:
        raise ValueError("Plot one model per file; do not pool different models.")

    points: dict[str, list[tuple[int, float, float, float]]] = defaultdict(list)
    for (condition, distance), values in grouped.items():
        successes = sum(values)
        total = len(values)
        accuracy = successes / total
        low, high = wilson_interval(successes, total)
        points[condition].append((distance, accuracy, low, high))

    for condition in points:
        points[condition].sort()

    return points


def plot_accuracy(
    points: dict[str, list[tuple[int, float, float, float]]],
    output: Path,
    *,
    title: str,
) -> None:
    fig, axis = plt.subplots(figsize=(9, 5.5))

    styles = {
        "last_window": {"label": "Last Window Only", "marker": "o"},
        "rolling_kv": {"label": "Rolling KV", "marker": "s"},
        "full_prompt": {"label": "Full Prompt", "marker": "^"},
    }

    for condition in ("last_window", "rolling_kv", "full_prompt"):
        if condition not in points:
            continue
        distances = [point[0] for point in points[condition]]
        accuracies = [point[1] for point in points[condition]]
        lows = [max(0.0, point[1] - point[2]) for point in points[condition]]
        highs = [max(0.0, point[3] - point[1]) for point in points[condition]]
        style = styles[condition]
        axis.errorbar(
            distances,
            accuracies,
            yerr=[lows, highs],
            marker=style["marker"],
            capsize=4,
            linewidth=2,
            label=style["label"],
        )

    all_distances = [
        point[0]
        for condition_points in points.values()
        for point in condition_points
    ]
    axis.axhline(0.25, color="gray", linestyle="--", linewidth=1, label="4-choice chance")
    if all_distances and min(all_distances) > 0:
        axis.set_xscale("log", base=2)
    elif all_distances:
        axis.set_xticks(sorted(set(all_distances)))
    axis.set_ylim(-0.02, 1.05)
    axis.set_xlabel("Code offset from final raw-window start (tokens)")
    axis.set_ylabel("Forced-choice accuracy")
    axis.set_title(title)
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot rolling KV experiment results.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="Rolling KV vs Last Window Accuracy")
    return parser.parse_args()


if __name__ == "__main__":
    main()

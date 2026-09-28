from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist, mean

import matplotlib.patheffects as path_effects
from matplotlib.lines import Line2D

from plot_marker_heatmap import plt
from totb.evaluate import wilson_interval


def main():
    parser = argparse.ArgumentParser(description="Seven-panel fixed-grid result figure")
    parser.add_argument("--experiment-dir", default="experiments/03_definition_to_carrier")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    directory = Path(args.experiment_dir)
    models = ["Qwen2.5-0.5B-Instruct", "Qwen2.5-3B-Instruct", "Mistral-7B-Instruct-v0.1",
              "Meta-Llama-3.1-8B-Instruct", "Muse-Glimmer-30B"]
    labels = ["Qwen 0.5B", "Qwen 3B", "Mistral 7B", "Llama 8B", "Glimmer 30B (NF4)"]
    cells = defaultdict(list)
    for model in models:
        for kind in ("rolling", "controls"):
            with (directory / "results" / kind / (model + ".csv")).open() as handle:
                for row in csv.DictReader(handle):
                    cells[model, row["condition"], int(row["definition_gap"]), int(row["boundary_offset"])].append(int(row["correct"]))
    gaps, offsets = [32, 64, 128, 256, 512, 768, 1024], [-32, 0, 32, 64, 128, 256]
    for model in models:
        for condition, count in (("rolling_kv", 100), ("last_window", 20), ("full_prompt", 20)):
            for gap in gaps:
                for offset in offsets:
                    if len(cells[model, condition, gap, offset]) != count:
                        raise ValueError("Expected complete official grid with n=100 rolling and n=20 controls")
    panels = [("Last Window: model mean", "last_window", models), ("Full Prompt: model mean", "full_prompt", models)]
    panels += [(f"Rolling KV: {label}", "rolling_kv", [model]) for model, label in zip(models, labels)]
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "pdf.fonttype": 42})
    figure, axes = plt.subplots(2, 4, figsize=(15, 8.1), layout="constrained")
    vertical_boundary = gaps.index(256) + 0.5
    horizontal_boundary = offsets.index(0) + 0.5

    def draw_boundaries(axis):
        for line in (axis.axvline(vertical_boundary, color="black", linestyle=":", linewidth=1.3),
                     axis.axhline(horizontal_boundary, color="black", linestyle=":", linewidth=1.3)):
            line.set_path_effects([path_effects.Stroke(linewidth=2.5, foreground="white"),
                                   path_effects.Normal()])

    summaries = []
    for axis, (title, condition, members) in zip(axes.flat, panels):
        matrix = []
        for offset in offsets:
            values = []
            for gap in gaps:
                groups = [cells[model, condition, gap, offset] for model in members]
                z = NormalDist().inv_cdf(1 - 0.05 / (2 * len(members)))
                intervals = [wilson_interval(sum(group), len(group), z=z) for group in groups]
                accuracy = mean(mean(group) for group in groups)
                values.append(accuracy)
                summaries.append([title, condition, gap, offset, len(members), len(groups[0]), accuracy,
                                  mean(interval[0] for interval in intervals), mean(interval[1] for interval in intervals)])
            matrix.append(values)
        image = axis.imshow(matrix, origin="lower", aspect="auto", vmin=0, vmax=1, cmap="viridis")
        axis.set_title(title)
        axis.set_xticks(range(len(gaps)), gaps, rotation=45)
        axis.set_yticks(range(len(offsets)), offsets)
        axis.set_xlabel("Definition → carrier gap (tokens)")
        axis.set_ylabel("Code-relative offset (tokens)")
        draw_boundaries(axis)
        for row_index, values in enumerate(matrix):
            for column_index, value in enumerate(values):
                axis.text(column_index, row_index, f"{value:.2f}", ha="center", va="center",
                          fontsize=7, color="black" if value > .62 else "white")
    key = axes.flat[-1]
    key.set_title("Quadrant guide (final raw window)")
    key.set_xlim(-0.5, len(gaps) - 0.5)
    key.set_ylim(-0.5, len(offsets) - 0.5)
    key.set_xticks(range(len(gaps)), gaps, rotation=45)
    key.set_yticks(range(len(offsets)), offsets)
    key.set_xlabel("Definition → carrier gap (tokens)")
    key.set_ylabel("Code-relative offset (tokens)")
    draw_boundaries(key)
    for center_x, gap_label in ((1.5, "Gap <512 tokens"), (5, "Gap ≥512 tokens")):
        key.text(center_x, 0.5, "Code visible\n" + gap_label,
                 ha="center", va="center", fontsize=8)
        key.text(center_x, 3.5, "Code evicted\nDefinition evicted\n" + gap_label,
                 ha="center", va="center", fontsize=8)
    figure.legend(handles=[
        Line2D([], [], color="black", linestyle=":", label="Dotted guides: offset 0 / 32; gap 256 / 512"),
        Line2D([], [], linestyle="none", label="W = 512 · Four-choice chance = 0.25"),
        Line2D([], [], linestyle="none", label="Rolling KV: 100 trials/model/cell · Controls: 20 trials/model/cell"),
        Line2D([], [], linestyle="none", label="Controls: equal-weight model means; per-model results and intervals supplied separately"),
    ], loc="outside lower center", ncol=2, frameon=False, fontsize=9,
       columnspacing=2.0, handletextpad=0.6)
    figure.colorbar(image, ax=list(axes.flat), label="Forced-choice accuracy", shrink=.7)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    figure.savefig(output.with_suffix(".pdf"))
    with output.with_suffix(".csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["series", "condition", "definition_gap", "offset", "models", "n_per_model", "accuracy", "ci95_low", "ci95_high"])
        writer.writerows(summaries)
    plt.close(figure)
    print(f"Wrote seven panels and interval table: {output}")


if __name__ == "__main__":
    main()

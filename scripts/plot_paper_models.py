from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist, mean

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt

from totb.evaluate import wilson_interval


def main() -> None:
    parser = argparse.ArgumentParser(description="Model-averaged controls and individual Rolling KV curves.")
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--grayscale", action="store_true")
    args = parser.parse_args()
    if len(args.inputs) != len(args.labels) or not 1 <= len(args.inputs) <= 5:
        raise ValueError("Provide one label per input, up to five models.")
    datasets = []
    model_names = set()
    settings = set()
    for filename in args.inputs:
        grouped = defaultdict(list)
        names = set()
        with open(filename) as handle:
            for row in csv.DictReader(handle):
                names.add(row["model"])
                settings.add((row["window_size"], row["choices"], row["task"], row["filler"]))
                grouped[(row["condition"], int(row["distance"]))].append(int(row["correct"]))
        if len(names) != 1 or names & model_names:
            raise ValueError("Each file must contain a different single model.")
        model_names.update(names)
        datasets.append(grouped)
    if len(settings) != 1:
        raise ValueError("Window, choices, task and filler must match across inputs.")
    window, choices, task, filler = settings.pop()
    keys = set(datasets[0])
    if any(set(data) != keys for data in datasets):
        raise ValueError("All models must have identical conditions and offsets.")
    if len({len(values) for data in datasets for values in data.values()}) != 1:
        raise ValueError("Use equal trial counts; do not mix pilots and confirmations.")
    distances = sorted({offset for condition, offset in keys})
    if any((condition, offset) not in keys for condition in ("full_prompt", "last_window", "rolling_kv") for offset in distances):
        raise ValueError("All three conditions are required at every offset.")
    count = len(next(iter(datasets[0].values())))
    task_title = {"code": "Secret-code retrieval", "code_defined": "Longer code definition"}.get(task, task)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "serif", "font.size": 10, "pdf.fonttype": 42})
    fig, axis = plt.subplots(figsize=(9, 5.5))
    summaries = []

    def draw(label, condition, points, color, marker, linestyle, shift=0, control=False):
        horizontal = [offset + shift for offset in distances]
        accuracy, lower, upper = zip(*points)
        axis.errorbar(horizontal, accuracy,
                      yerr=[[max(0, value - low) for value, low in zip(accuracy, lower)],
                            [max(0, high - value) for value, high in zip(accuracy, upper)]],
                      color=color, marker=marker, linestyle=linestyle,
                      linewidth=1.3 if control else 1.7, markersize=5,
                      markerfacecolor="white", markeredgewidth=1.1,
                      elinewidth=0.7, capsize=2, label=label, zorder=2 if control else 3)
        for offset, (value, low, high) in zip(distances, points):
            summaries.append(dict(series=label, condition=condition, distance=offset,
                                  accuracy=value, ci95_low=low, ci95_high=high))

    adjusted_z = NormalDist().inv_cdf(1 - 0.05 / (2 * len(datasets)))
    for condition, label, style, color in (
        ("last_window", "Last Window — model mean", "--", "0.45"),
        ("full_prompt", "Full Prompt — model mean", ":", "0.65"),
    ):
        points = []
        for offset in distances:
            values = [data[(condition, offset)] for data in datasets]
            intervals = [wilson_interval(sum(group), len(group), z=adjusted_z) for group in values]
            points.append((mean(mean(group) for group in values),
                           mean(low for low, high in intervals), mean(high for low, high in intervals)))
        draw(label, condition, points, color, None, style, control=True)
    markers = ("o", "s", "^", "D", "P")
    colors = ("#233b53", "#70432b", "#245746", "#563d68", "#262626")
    for index, (label, data) in enumerate(zip(args.labels, datasets)):
        points = []
        for offset in distances:
            values = data[("rolling_kv", offset)]
            points.append((mean(values), *wilson_interval(sum(values), len(values))))
        shift = (index - (len(datasets) - 1) / 2) * 0.08
        draw(f"Rolling KV: {label}", "rolling_kv", points,
             "0.15" if args.grayscale else colors[index], markers[index], "-", shift)
    axis.axhline(1 / int(choices), color="0.75", linewidth=0.8, linestyle="-.", label=f"Chance ({100 / int(choices):g}%)")
    axis.set(xticks=distances, ylim=(-0.02, 1.06),
             xlabel="Code offset from final raw-window start (tokens)", ylabel="Forced-choice accuracy",
             title=f"{task_title} · W = {window} · {count} trials per model and offset")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", alpha=0.12)
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.19), ncol=2, frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=240, bbox_inches="tight")
    fig.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    with output.with_suffix(".csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    output.with_suffix(".md").write_text(
        f"# Figure caption\n\n{len(datasets)} models; {count} trials per model and offset; W={window}. "
        "Neutral controls are equal-weight means of the included models' accuracies. "
        "Control error bars average the endpoints of Bonferroni-adjusted Wilson intervals "
        "(family = included models at a single condition and offset), giving conservative, "
        "approximate 95% intervals for the fixed-panel mean without assuming independence between models. "
        "Rolling KV error bars are individual pointwise 95% Wilson intervals. "
        "Intervals do not measure variability across a population of models, and are not simultaneous across offsets. "
        "Averaging can conceal model-specific control differences; retain the individual plots as supporting material. "
        "Markers are shifted horizontally by up to 0.16 tokens for visibility only. "
        "Offset +1 still allows direct code access in the final scoring cache; +2 does not.\n\n"
        + "\n".join(f"- {label}: `{filename}`" for label, filename in zip(args.labels, args.inputs)) + "\n"
    )
    print(f"Wrote {output} and PDF, summary CSV, caption Markdown")


if __name__ == "__main__":
    main()

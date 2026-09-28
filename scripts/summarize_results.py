from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from totb.evaluate import wilson_interval


def main():
    parser = argparse.ArgumentParser(description="Per-model per-cell accuracy and Wilson intervals")
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cells = defaultdict(list)
    for filename in args.inputs:
        with open(filename) as handle:
            for row in csv.DictReader(handle):
                cells[row["model"], row["condition"], int(row.get("definition_gap", -1)),
                      int(row.get("boundary_offset", row.get("distance")))].append(int(row["correct"]))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "condition", "definition_gap", "offset", "n", "accuracy", "ci95_low", "ci95_high"])
        for (model, condition, gap, offset), values in sorted(cells.items()):
            low, high = wilson_interval(sum(values), len(values))
            writer.writerow([model, condition, "" if gap == -1 else gap, offset, len(values), sum(values) / len(values), low, high])
    print(f"Wrote {len(cells)} cell summaries to {path}")


if __name__ == "__main__":
    main()

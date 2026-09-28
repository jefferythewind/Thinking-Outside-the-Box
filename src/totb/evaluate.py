from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class Row:
    condition: str
    distance: int
    correct: bool


def summarize(rows: list[Row]) -> str:
    grouped: dict[tuple[str, int], list[bool]] = defaultdict(list)
    for row in rows:
        grouped[(row.condition, row.distance)].append(row.correct)

    lines = ["condition,distance,n,accuracy,ci95_low,ci95_high"]
    for condition, distance in sorted(grouped):
        values = grouped[(condition, distance)]
        accuracy = mean(values)
        low, high = wilson_interval(sum(values), len(values))
        lines.append(
            f"{condition},{distance},{len(values)},{accuracy:.4f},{low:.4f},{high:.4f}"
        )
    return "\n".join(lines)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0

    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z
        * ((proportion * (1 - proportion) + z**2 / (4 * total)) / total) ** 0.5
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)

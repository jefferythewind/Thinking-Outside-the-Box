from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from totb.artifacts import read_trials


def main():
    root = Path(__file__).resolve().parents[1]
    directories = sorted((root / "experiments").iterdir())
    assert len(directories) == 3
    for directory in directories:
        manifest = json.loads((directory / "MANIFEST.json").read_text())
        for entry in manifest["files"]:
            path = directory / entry["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], path
        config = json.loads((directory / "configs/run.json").read_text())
        for item in config["models"]:
            metadata_path = directory / item["metadata"]
            recorded = json.loads(metadata_path.read_text())["arguments"]
            for key, value in {**config["arguments"], **item.get("arguments", {})}.items():
                assert recorded.get(key) == value, (item["name"], key)
            source = metadata_path.with_name(metadata_path.name.replace(".metadata.json", ".csv"))
            with source.open() as handle:
                rows = list(csv.DictReader(handle))
            grid = directory.name.startswith("03")
            expected = 4200 if grid else 3300 if directory.name.startswith("01") else 6300
            assert len(rows) == expected
            keys = [(row["trial"], row["condition"]) for row in rows]
            assert len(set(keys)) == len(keys)
            counts = Counter((row["condition"], row.get("definition_gap", ""), row.get("boundary_offset", row.get("distance"))) for row in rows)
            assert all(count == 100 for count in counts.values())
            if not grid:
                assert {row['condition'] for row in rows} == {'last_window', 'full_prompt', 'rolling_kv'}
                continue
            trials = read_trials(source)
            assert len(trials) == 4200
            by_id = {trial["trial"]: trial for trial in trials}
            assert len(by_id) == 4200
            for row in rows:
                trial = by_id[int(row["trial"])]
                assert trial['answer_token_id'] == int(row['answer_token_id'])
                assert len(trial['prompt_token_ids']) == int(row['prompt_tokens'])
                assert len(trial['prompt_token_ids']) - 512 - trial['answer_token_index'] == int(row['boundary_offset'])
            cells = defaultdict(list)
            for trial in trials:
                cells[trial["definition_gap"], trial["boundary_offset"]].append(trial)
            generator = random.Random(2026)
            selected = {trial["trial"] for cell, group in sorted(cells.items())
                        for trial in generator.sample(sorted(group, key=lambda trial: trial["trial"]), 20)}
            control = directory / "results/controls" / source.name
            with control.open() as handle:
                control_rows = list(csv.DictReader(handle))
            assert len(control_rows) == 1680
            assert len({(row['trial'], row['condition']) for row in control_rows}) == 1680
            for condition in ("last_window", "full_prompt"):
                assert {int(row['trial']) for row in control_rows if row['condition'] == condition} == selected
            saved_controls = read_trials(control)
            assert len(saved_controls) == len(selected)
            for trial in saved_controls:
                assert trial['trial'] in selected
                assert trial['prompt_token_ids'] == by_id[trial['trial']]['prompt_token_ids']
        print(f"{directory.name}: hashes, counts, unique trials and saved controls verified")


if __name__ == "__main__":
    main()

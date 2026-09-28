from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from transformers import AutoTokenizer

from totb.dataset import build_trials


def main():
    parser = argparse.ArgumentParser(description="Regenerate verified examples from experiment 1/2 metadata")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.input)
    metadata = json.loads(source.with_suffix(".metadata.json").read_text())
    settings = metadata["arguments"]
    tokenizer = AutoTokenizer.from_pretrained(settings["model"], revision=metadata["resolved_model_revision"], local_files_only=True)
    trials = build_trials(tokenizer, num_trials=settings["trials"], window_size=settings["window_size"],
                          distances=list(map(int, settings["distances"].split(","))), num_choices=settings["choices"],
                          filler_variant=settings["filler"], task=settings["task"], seed=settings["seed"])
    with source.open() as handle:
        rows = {int(row["trial"]): row for row in csv.DictReader(handle) if row["condition"] == "rolling_kv"}
    assert len(rows) == len(trials)
    selected = {}
    for index, trial in enumerate(trials, 1):
        row = rows[index]
        assert int(row["answer_token_id"]) == trial.answer_token_id
        assert int(row["secret_token_index"]) == trial.secret_token_index
        assert int(row["prompt_tokens"]) == len(trial.prompt_token_ids)
        assert int(row["distance"]) == trial.distance_outside_window
        assert list(map(int, row["candidate_token_ids"].split())) == list(trial.candidate_token_ids)
        selected.setdefault(trial.distance_outside_window, (index, trial))
    lines = [f"# Actual contexts: {source.stem}", "", f"Source: `{source}`.",
             "Regenerated with the pinned tokenizer and saved settings; all trials checked against CSV indices, lengths, answers and candidates.",
             "First trial per offset shown. These are actual model-specific examples, not cross-model identical prompts."]
    for offset, (index, trial) in sorted(selected.items()):
        tokens = trial.prompt_token_ids
        start = len(tokens) - settings["window_size"]
        decode = lambda ids: tokenizer.decode(list(ids), skip_special_tokens=False, clean_up_tokenization_spaces=False)
        lines.extend(["", f"## Offset {offset}; trial {index}", "",
                      f"Expected answer: `{trial.answer_text}`; candidate IDs: {list(trial.candidate_token_ids)}.",
                      f"Code index {trial.secret_token_index}; raw window [{start}, {len(tokens)}); final scoring cache [{max(0,start-1)}, {len(tokens)-1}).",
                      "", "### Full input including question", "```text", decode(tokens), "```",
                      "### Final raw input", "```text", decode(tokens[start:]), "```"])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    print(f"Verified {len(trials)} trials; exported {len(selected)} contexts")


if __name__ == "__main__":
    main()

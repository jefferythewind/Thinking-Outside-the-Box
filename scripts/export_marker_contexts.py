from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer
from totb.artifacts import read_trials


def main():
    parser = argparse.ArgumentParser(description="Export actual saved marker prompts, not regenerated examples.")
    parser.add_argument("--input", required=True, help="Prediction CSV with sibling trials.jsonl and metadata.json")
    parser.add_argument("--pair", type=int, help="Optional matched-pair diagnostic; default first saved trial per cell")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.input)
    metadata = json.loads(source.with_suffix(".metadata.json").read_text())
    tokenizer = AutoTokenizer.from_pretrained(metadata["arguments"]["model"],
                                            revision=metadata["resolved_model_revision"], local_files_only=True)
    window = metadata["arguments"]["window_size"]
    predictions = {int(row["trial"]): row for row in csv.DictReader(source.open()) if row["condition"] == "rolling_kv"}
    trials = read_trials(source)
    if args.pair is not None:
        trials = [trial for trial in trials if trial.get("matched_pair_id") == args.pair]
    else:
        cells = {}
        for trial in sorted(trials, key=lambda trial: trial["trial"]):
            cells.setdefault((trial["definition_gap"], trial["boundary_offset"]), trial)
        trials = list(cells.values())
    trials = sorted(trials, key=lambda trial: (trial["boundary_offset"], trial["definition_gap"]))
    if not trials:
        raise ValueError("No saved trials match the selection")
    decode = lambda ids: tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    digest = lambda ids: hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:16]
    lines = [f"# Actual contexts: {source.stem}", "",
             f"Source: `{source}`. W={window}. Zero-based indices; ranges [start,end).",
             "Selection: first saved trial per cell unless a matched pair was explicitly requested. Cells need not share an answer.",
             "These are decoded from the exact saved input token IDs, not reconstructed by retokenizing text.",
             "Full prompt and final raw window are unabridged. KV text labels identify cached positions,",
             "not their numerical states. Identical raw windows need not have identical contextualized KV states.", "",
             "| Gap | Offset | Trial | Code index | Code-attention start | Raw start | Final-window token hash | Prediction | Correct |",
             "|---:|---:|---:|---:|---:|---:|---|---|---|"]
    bodies = []
    for trial in trials:
        ids = trial["prompt_token_ids"]
        answer = trial["answer_token_index"]
        end = trial["preamble_end_index"]
        marker = trial["carrier_start_index"]
        raw_start = len(ids) - window
        cache_start = max(0, raw_start - 1)
        code_start = max(0, answer - window)
        row = predictions[trial["trial"]]
        assert int(row["answer_token_id"]) == trial["answer_token_id"]
        assert raw_start - answer == trial["boundary_offset"]
        predicted = decode([int(row["predicted_token_id"])])
        lines.append(f"| {trial['definition_gap']} | {trial['boundary_offset']} | {trial['trial']} | {answer} | {code_start} | {raw_start} | `{digest(ids[raw_start:])}` | `{predicted}` | {row['correct']} |")
        bodies.extend([
            "", f"## Gap {trial['definition_gap']}, offset {trial['boundary_offset']} — trial {trial['trial']}", "",
            f"Expected: `{trial['answer_text']}` (token {trial['answer_token_id']}); predicted: `{predicted}`.",
            f"Marker: `{trial['marker_text']}`. Candidates: {[(token, decode([token])) for token in trial['candidate_token_ids']]!r}.",
            f"Preamble ends at {end} exclusive; marker begins {marker}; code at {answer}; total tokens {len(ids)}.",
            f"Code computation can attend [{code_start},{answer}). Final raw window [{raw_start},{len(ids)}).",
            f"Final scoring KV positions [{cache_start},{len(ids)-1}); current input token is {len(ids)-1}.",
            "", "### Text immediately preceding marker (last 24 tokens)", "```text", decode(ids[marker-24:marker]), "```",
            "### Start of code-computation attention span (first 32 tokens)", "```text", decode(ids[code_start:code_start+32]), "```",
            "### Token-level boundary inspection", "", "| Index | Token ID | Decoded token (JSON) |", "|---:|---:|---|"])
        indices = sorted(set(range(max(0,end-7),end+8)) | set(range(max(0,code_start-3),code_start+8)) | set(range(marker,answer+2)))
        for index in indices:
            bodies.append(f"| {index} | {ids[index]} | `{json.dumps(decode([ids[index]]))}` |")
        bodies.extend(["", "### Full input, including question", "```text", decode(ids), "```",
                       "### Final raw window (Last Window input)", "```text", decode(ids[raw_start:]), "```",
                       "### Final scoring KV start (first 32 cached-position tokens)", "```text",
                       decode(ids[cache_start:cache_start+32]), "```"])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines + bodies) + "\n")
    print(f"Wrote {len(trials)} actual contexts to {output}")
    for offset in sorted({trial['boundary_offset'] for trial in trials}):
        subset = [trial for trial in trials if trial['boundary_offset'] == offset]
        print(f"Offset {offset}: {len(set(digest(trial['prompt_token_ids'][-window:]) for trial in subset))} unique raw windows across {len(subset)} gaps")


if __name__ == "__main__":
    main()

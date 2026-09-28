from __future__ import annotations

import gzip
import json


def read_trials(source):
    path = source.with_suffix(".trials.jsonl")
    if path.exists():
        handle = path.open()
    else:
        handle = gzip.open(source.with_suffix(".trials.jsonl.gz"), "rt")
    with handle:
        return [json.loads(line) for line in handle]

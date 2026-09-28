from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run a pinned paper configuration without overwriting curated results")
    parser.add_argument("--experiment", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--models", nargs="+", help="Optional model basenames from the configuration")
    parser.add_argument("--glimmer-python", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folders = {1: "01_secret_code", 2: "02_code_defined", 3: "03_definition_to_carrier"}
    directory = root / "experiments" / folders[args.experiment]
    config = json.loads((directory / "configs/run.json").read_text())
    output = Path(args.output).resolve()
    if output.is_relative_to(root / "experiments"):
        raise ValueError("Write new runs outside curated experiments/")
    models = [item for item in config["models"] if not args.models or item["name"] in args.models]
    if not models or args.models and set(args.models) != {item["name"] for item in models}:
        raise ValueError("Unknown model selection")
    for item in models:
        if any(output.glob(item["name"] + ".*")):
            raise FileExistsError(f"Existing output for {item['name']}")
    if not args.dry_run:
        output.mkdir(parents=True, exist_ok=True)
    inputs, labels = [], []
    for item in models:
        metadata = json.loads((directory / item["metadata"]).read_text())
        recorded = metadata["arguments"]
        target = output / (item["name"] + ".csv")
        executable = args.glimmer_python if recorded.get("load_in_4bit", False) else sys.executable
        command = [executable, str(root / "scripts" / config["runner"])]
        settings = {**config["arguments"], **item.get("arguments", {}), "model": recorded["model"],
                    "revision": metadata["resolved_model_revision"], "output": str(target)}
        if args.experiment == 3:
            settings["batch_size"] = item["batch_size"]
        if recorded.get("load_in_4bit", False):
            settings["load_in_4bit"] = True
        for key, value in settings.items():
            if value is True:
                command.append("--" + key.replace("_", "-"))
            elif value is not False and value is not None:
                command.append("--" + key.replace("_", "-") + "=" + str(value))
        print(shlex.join(command), flush=True)
        if not args.dry_run:
            subprocess.run(command, cwd=root, check=True)
            plotter = "plot_marker_heatmap.py" if args.experiment == 3 else "plot_results.py"
            subprocess.run([sys.executable, str(root / "scripts" / plotter), "--input", str(target),
                            "--output", str(target.with_suffix(".png")), "--title", item["label"]], cwd=root, check=True)
        inputs.append(str(target))
        labels.append(item["label"])
    if not args.dry_run and args.experiment in (1, 2):
        subprocess.run([sys.executable, str(root / "scripts/plot_paper_models.py"), "--inputs", *inputs,
                        "--labels", *labels, "--output", str(output / "comparison.png")], cwd=root, check=True)


if __name__ == "__main__":
    main()

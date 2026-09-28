from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, MuseGlimmerForConditionalGeneration


def add_model_options(parser) -> None:
    parser.add_argument("--revision", default="main")
    parser.add_argument("--load-in-4bit", action="store_true", help="Experimental NF4 weights; requires bitsandbytes.")
    parser.add_argument("--full-prompt", action="store_true", help="Also score the entire prompt as a task-solvability reference.")


def load_model(args):
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    config = AutoConfig.from_pretrained(args.model, revision=args.revision)
    loader = MuseGlimmerForConditionalGeneration if config.model_type == "muse_glimmer" else AutoModelForCausalLM
    loading_options = {}
    if args.load_in_4bit:
        loading_options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16,
        )
    model = loader.from_pretrained(
        args.model,
        revision=args.revision,
        torch_dtype="auto" if args.dtype == "auto" else getattr(torch, args.dtype),
        device_map=args.device_map,
        **loading_options,
    ).eval()
    if args.output:
        path = Path(args.output).with_suffix(".metadata.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "arguments": vars(args),
            "resolved_model_revision": getattr(model.config, "_commit_hash", None),
            "model_config": model.config.to_dict(),
            "actual_dtype": str(model.dtype),
            "quantization": "bitsandbytes NF4 double quantization; BF16 compute" if args.load_in_4bit else "none",
            "bitsandbytes_version": importlib.metadata.version("bitsandbytes") if args.load_in_4bit else None,
            "loader_class": type(model).__name__,
            "attention_implementation": model.config._attn_implementation,
            "tokenizer_class": type(tokenizer).__name__,
            "prompt_format": "raw completion; no chat template",
            "independent_batch_size": getattr(args, "batch_size", 1),
            "batch_policy": "equal-length independent prompts; no padding; no cross-prompt attention",
            "cache_policy": "plain DynamicCache; crop after each step; W prior positions plus current token",
            "position_policy": "absolute position_ids" if not args.no_cache_position else "cache-derived positions (ablation)",
            "packages": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "accelerate")},
            "source_sha256": source_hashes(),
        }
        path.write_text(json.dumps(metadata, indent=2, default=str) + "\n")
    return tokenizer, model


def source_hashes():
    root = Path(__file__).resolve().parents[2]
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for directory in (root / "src", root / "scripts", root / "tests")
            for path in sorted(directory.rglob("*.py"))}

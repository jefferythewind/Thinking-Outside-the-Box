# Models and numerical settings

The three experiments use the same panel. Exact immutable revisions and full
configurations are in result metadata; the launcher reads those pinned revisions.

| Model ID | Precision | Native attention configuration |
|---|---|---|
| `Qwen/Qwen2.5-0.5B-Instruct` | BF16 | Full |
| `Qwen/Qwen2.5-3B-Instruct` | BF16 | Full |
| `mistralai/Mistral-7B-Instruct-v0.1` | BF16 | Sliding, 4096 tokens |
| `meta-llama/Meta-Llama-3.1-8B-Instruct` | BF16 | Full |
| `meta-models/Muse-Glimmer-30B` | NF4 double quantization; BF16 compute | Three local 2048-token layers per global layer |

Native spans differ from the W=512 experimental eviction policy. Glimmer uses
`MuseGlimmerForConditionalGeneration`, text inputs only; all local/global caches
are cropped. Quantization differs across models and remains explicit in labels.

Runs used an RTX 3090 (24 GB), PyTorch 2.6.0+cu124, Transformers 5.16.1,
Accelerate 1.12.0 and, for Glimmer, bitsandbytes 0.50.2. Individual metadata
is authoritative. Install a CUDA PyTorch build appropriate for your machine
before installing this project. Optional Glimmer dependencies:
`python -m pip install -e '.[glimmer]'`. Pass `--glimmer-python PATH` to use
a separate environment for that model.

Model access may require authentication and license acceptance. No weights
or credentials are distributed. Each model uses its own tokenizer and raw
completion formatting; candidate IDs must not be transferred between models.
Full Prompt retains native architectural attention rules.

# Experimental methods

All tasks use raw completion prompts (no chat template), neutral filler,
W=512, and four tokenizer-specific single-token code candidates. Candidate
answers are scored from next-token logits, not printed in the question.
Accuracy is argmax correctness; chance is 25%. No model training is performed.

## Conditions and offsets

- **Last Window Only:** recompute the final W input IDs, starting positions at zero.
- **Full Prompt:** score all input IDs in one forward, subject to native attention rules.
- **Rolling KV:** prefill W tokens, then ingest every subsequent token in order.
  Keep the newest W KV positions after every step in every layer, including
  Glimmer's global layers. Supply absolute positions. The current token can
  attend W prior positions before cropping.

With prompt length N and code index A, offset is `(N - W) - A`. At −32 the
code is 32 tokens inside the final raw window; at 0 it is its first token.
At +1 the code is outside the raw window but still directly accessible during
final cached scoring. At +2 and beyond it is absent from both. Context examples
show cached position labels, not numerical KV tensors.

## Tasks

1. Secret code: defining phrase `The secret code is:`.
2. Longer definition: defining phrase `The secret code is defined by the following identifier:`.
3. Definition-to-carrier gap: a preamble designates an arbitrary marker;
   after D filler tokens the marker is followed by the code. Tail filler
   independently controls the code-relative offset. D counts filler IDs from
   the exclusive preamble end to the carrier prefix, not the entire span to
   the code; the tokenized marker prefix also contributes to that span.

Experiment 3 has 128 leading filler tokens. Its numeric grid replaces the
old tokenizer-dependent B diagnostic. At gap 32, offset −32, some definition
tokens may remain visible; use stored indices to establish exact visibility.

## Batching and controls

Experiments 1/2 use serial scoring of all conditions, 100 trials/offset/model,
seed 1. Experiment 3 uses seed 2 and independent equal-length batches for
Rolling KV (four prompts; two for NF4 Glimmer). No padding, cross-prompt
attention, shared states, token blocking, or altered masks are used. Each
row still advances one token per step. Remainders may have smaller batches.

Experiment 3 controls use the same 20 prompts per cell/model sampled without
replacement from its saved 100 rolling prompts. Selection uses Python Random
seed 2026, sorted numeric cells and sorted original trial IDs, never correctness.
Both controls run serially. Seeds do not imply identical prompts across tokenizers.

## Reporting

Raw CSVs include correctness, answer/prediction IDs, candidates and boundary
indices. Metadata records model revisions, precision, packages and source hashes.
Individual intervals are pointwise 95% Wilson intervals, not simultaneous
grid-wide bounds. Combined controls are equal-weight model means. Their interval
averages endpoints of per-model Wilson intervals with Bonferroni-adjusted z for
five models, matching the line plots: a conservative approximate interval for
this fixed panel, not variability over all possible models. Per-model controls
remain available.

Batching is not bit-exact: a pretrained Mistral replay agreed on 329/330
predictions. Tiny-model FP32 checks cover all four architectures, not pretrained
NF4 equivalence. Hardware, precision and kernels may change close decisions.

# Figure caption

5 models; 100 trials per model and offset; W=512. Neutral controls are equal-weight means of the included models' accuracies. Control error bars average the endpoints of Bonferroni-adjusted Wilson intervals (family = included models at a single condition and offset), giving conservative, approximate 95% intervals for the fixed-panel mean without assuming independence between models. Rolling KV error bars are individual pointwise 95% Wilson intervals. Intervals do not measure variability across a population of models, and are not simultaneous across offsets. Averaging can conceal model-specific control differences; retain the individual plots as supporting material. Markers are shifted horizontally by up to 0.16 tokens for visibility only. Offset +1 still allows direct code access in the final scoring cache; +2 does not.

- Qwen 0.5B: `runs/experiment2_five_models/Qwen2.5-0.5B-Instruct.csv`
- Qwen 3B: `runs/experiment2_five_models/Qwen2.5-3B-Instruct.csv`
- Mistral 7B: `runs/experiment2_five_models/Mistral-7B-Instruct-v0.1.csv`
- Llama 8B: `runs/experiment2_five_models/Meta-Llama-3.1-8B-Instruct.csv`
- Glimmer 30B (NF4): `runs/experiment2_five_models/Muse-Glimmer-30B.csv`

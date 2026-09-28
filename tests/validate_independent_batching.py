from __future__ import annotations

from types import SimpleNamespace

import torch
from transformers import (
    LlamaConfig, LlamaForCausalLM, MistralConfig, MistralForCausalLM,
    MuseGlimmerConfig, MuseGlimmerForConditionalGeneration,
    Qwen2Config, Qwen2ForCausalLM,
)

from scripts.run_marker_grid import score_trials
from totb.runner import score_rolling_kv
from totb.runner_batched import score_rolling_kv_batched


@torch.inference_mode()
def main():
    torch.set_num_threads(1)
    torch.manual_seed(11)
    common = dict(vocab_size=64, hidden_size=32, intermediate_size=64,
                  num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
                  head_dim=8, bos_token_id=62, eos_token_id=63)
    configurations = [
        (Qwen2ForCausalLM, Qwen2Config(**common)),
        (MistralForCausalLM, MistralConfig(**common, sliding_window=32)),
        (LlamaForCausalLM, LlamaConfig(**common)),
        (MuseGlimmerForConditionalGeneration, MuseGlimmerConfig(
            text_config={**common, "num_hidden_layers": 4,
                         "layer_types": ["sliding_attention"] * 3 + ["full_attention"],
                         "layer_rope_theta": [500000.0] * 3 + [0]},
            vision_config=dict(hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                               num_attention_heads=4, layer_types=["full_attention"]),
            image_token_id=60, video_token_id=61, out_hidden_size=32, projector_hidden_size=32,
        )),
    ]
    for model_class, config in configurations:
        config._attn_implementation = "eager"
        model = model_class(config).eval()
        for backend in ("eager", "sdpa"):
            model.set_attn_implementation(backend)
            for length in (5, 8, 9, 39):
                prompts = torch.randint(0, 50, (4, length)).tolist()
                candidates = [[50, 51, 52, 53]] * 4
                actual = score_rolling_kv_batched(model, prompts, candidates, window_size=8)
                for prompt, candidate, scores in zip(prompts, candidates, actual, strict=True):
                    expected = score_rolling_kv(model, prompt, candidate, window_size=8)
                    torch.testing.assert_close(torch.tensor(list(scores.values())),
                                               torch.tensor(list(expected.values())), atol=1e-5, rtol=1e-5)
            trials = [SimpleNamespace(prompt_token_ids=torch.randint(0, 50, (length,)).tolist(),
                                      candidate_token_ids=[50, 51, 52, 53])
                      for length in (12, 9, 12, 9, 12)]
            args = SimpleNamespace(batch_size=2, rolling_block_size=1, no_cache_position=False, window_size=8)
            grouped = list(score_trials(model, trials, args))
            assert sorted(index for index, trial, scores, size in grouped) == [1, 2, 3, 4, 5]
            assert sorted(size for index, trial, scores, size in grouped) == [1, 2, 2, 2, 2]
            for index, trial, scores, size in grouped:
                assert trial is trials[index - 1]
                expected = score_rolling_kv(model, trial.prompt_token_ids, trial.candidate_token_ids, window_size=8)
                torch.testing.assert_close(torch.tensor(list(scores.values())),
                                           torch.tensor(list(expected.values())), atol=1e-5, rtol=1e-5)
        print(f"{model_class.__name__}: serial/batched FP32 agreement; eager/SDPA; grouping and remainder pass")


if __name__ == "__main__":
    main()

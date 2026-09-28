from __future__ import annotations

import torch
from transformers import LlamaConfig, LlamaForCausalLM, MistralConfig, MistralForCausalLM, Qwen2Config, Qwen2ForCausalLM

from totb.runner import score_rolling_kv


@torch.inference_mode()
def main() -> None:
    for config_class, model_class in (
        (Qwen2Config, Qwen2ForCausalLM),
        (MistralConfig, MistralForCausalLM),
        (LlamaConfig, LlamaForCausalLM),
    ):
        torch.manual_seed(11)
        config = config_class(
            vocab_size=64,
            hidden_size=32,
            intermediate_size=64,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
        )
        config._attn_implementation = "eager"
        model = model_class(config).eval()
        tokens = torch.arange(1, 25).unsqueeze(0)
        positions = torch.arange(24)
        for window_size in (1, 8, 16):
            separation = positions[:, None] - positions[None, :]
            allowed = (separation >= 0) & (separation <= window_size)
            mask = torch.zeros(24, 24).masked_fill(~allowed, torch.finfo(torch.float32).min)
            logits = model(input_ids=tokens, attention_mask=mask[None, None], use_cache=False).logits
            expected = torch.log_softmax(logits[0, -1, 30:34], dim=0)
            actual = torch.tensor(list(score_rolling_kv(
                model, tokens[0].tolist(), range(30, 34), window_size=window_size,
            ).values()))
            torch.testing.assert_close(actual, expected, atol=1e-6, rtol=1e-5)
        print(f"{model_class.__name__}: rolling cache matches independent banded forward")


if __name__ == "__main__":
    main()

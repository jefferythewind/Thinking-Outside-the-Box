from __future__ import annotations

from unittest.mock import patch

import torch
from transformers import MuseGlimmerConfig, MuseGlimmerForConditionalGeneration

from totb import runner


@torch.inference_mode()
def main() -> None:
    torch.manual_seed(11)
    torch.set_num_threads(1)
    config = MuseGlimmerConfig(
        text_config=dict(vocab_size=64, hidden_size=32, intermediate_size=64,
                         num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2,
                         head_dim=8, layer_types=["sliding_attention"] * 3 + ["full_attention"],
                         layer_rope_theta=[500000.0] * 3 + [0], bos_token_id=62, eos_token_id=63),
        vision_config=dict(hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                           num_attention_heads=4, layer_types=["full_attention"]),
        image_token_id=60, video_token_id=61, out_hidden_size=32, projector_hidden_size=32,
    )
    config._attn_implementation = "eager"
    model = MuseGlimmerForConditionalGeneration(config).eval()
    tokens = (torch.arange(550) % 50).unsqueeze(0)
    separation = torch.arange(550)[:, None] - torch.arange(550)[None, :]
    mask = torch.zeros(550, 550).masked_fill(
        (separation < 0) | (separation > 512), torch.finfo(torch.float32).min,
    )[None, None]
    expected = torch.log_softmax(model(input_ids=tokens, attention_mask=mask,
                                      use_cache=False).logits[0, -1, 50:54], dim=0)
    checks = []

    def validate(cache, window_size):
        assert len(cache.layers) == 4
        for layer in cache.layers:
            assert layer.keys.shape[-2] == window_size
            assert layer.values.shape[-2] == window_size
        checks.append(True)

    with patch.object(runner, "validate_cache_window", validate):
        actual = torch.tensor(list(runner.score_rolling_kv(
            model, tokens[0].tolist(), range(50, 54), window_size=512,
        ).values()))
    torch.testing.assert_close(actual, expected, atol=1e-5, rtol=1e-5)
    assert len(checks) == 39
    print("Glimmer: all local/global layers cropped to 512; matches independent banded forward.")


if __name__ == "__main__":
    main()

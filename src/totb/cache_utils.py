from __future__ import annotations

from typing import Any

import torch


def cache_length(cache: Any) -> int:
    if hasattr(cache, "get_seq_length"):
        return int(cache.get_seq_length())

    if isinstance(cache, (tuple, list)) and cache:
        first_layer = cache[0]
        key_states = first_layer[0]
        return int(key_states.shape[-2])

    return 0


def retain_newest_cache_positions(cache: Any, window_size: int) -> Any:
    length = cache_length(cache)
    if length <= window_size:
        return cache

    if hasattr(cache, "layers"):
        for layer in cache.layers:
            if hasattr(layer, "keys") and layer.keys is not None:
                layer.keys = layer.keys[..., -window_size:, :].contiguous()
            if hasattr(layer, "values") and layer.values is not None:
                layer.values = layer.values[..., -window_size:, :].contiguous()
        return cache

    if isinstance(cache, tuple):
        return tuple(_slice_legacy_layer(layer, window_size) for layer in cache)

    if isinstance(cache, list):
        return [_slice_legacy_layer(layer, window_size) for layer in cache]

    raise TypeError(f"Unsupported cache type: {type(cache)!r}")


def _slice_legacy_layer(layer: Any, window_size: int) -> Any:
    if len(layer) < 2:
        raise ValueError("Expected each cache layer to contain key and value tensors.")

    key_states = layer[0][..., -window_size:, :].contiguous()
    value_states = layer[1][..., -window_size:, :].contiguous()

    if isinstance(layer, tuple):
        return (key_states, value_states, *layer[2:])

    return [key_states, value_states, *layer[2:]]


def validate_cache_window(cache: Any, window_size: int) -> None:
    if hasattr(cache, "layers"):
        for index, layer in enumerate(cache.layers):
            for name in ("keys", "values"):
                tensor = getattr(layer, name, None)
                if tensor is not None and tensor.shape[-2] > window_size:
                    raise AssertionError(f"Layer {index} {name} exceeds window size {window_size}.")
    length = cache_length(cache)
    if length > window_size:
        raise AssertionError(f"Cache length {length} exceeds window size {window_size}.")


def tensorize_token(token_id: int, device: torch.device) -> torch.Tensor:
    return torch.tensor([[token_id]], dtype=torch.long, device=device)


def tensorize_position(position: int, device: torch.device) -> torch.Tensor:
    return torch.tensor([position], dtype=torch.long, device=device)

"""Reproducibility seed management for consistent clustering results."""

from __future__ import annotations

import random
from typing import Optional

import numpy as np

FIXED_SEED: int = 42


def get_seed(consistent: bool) -> Optional[int]:
    """Return a fixed seed if consistency is requested, otherwise None."""
    return FIXED_SEED if consistent else None


def apply_seed(seed: Optional[int]) -> None:
    """Set random seeds across stdlib, numpy, and torch if seed is not None."""
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass

"""
LLM Evaluation Benchmark Dataset Loader (Phase 2 Externalized Dataset)
Loads benchmark cases from external JSON datasets under backend/eval/datasets/
"""

import os
import json
from typing import List, Dict, Any, Optional

DATASET_VERSION_V2 = "v2.0.0"

DEFAULT_DATASET_FILE = os.path.join(os.path.dirname(__file__), "datasets", "benchmark_v2.json")

def load_benchmark_dataset(
    file_path: Optional[str] = None,
    include_disabled: bool = False
) -> List[Dict[str, Any]]:
    """
    Loads benchmark evaluation cases from external JSON dataset.
    Filters out disabled cases (e.g. enabled=False) unless include_disabled=True.
    """
    target_path = file_path or DEFAULT_DATASET_FILE

    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Benchmark dataset file not found at: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        cases: List[Dict[str, Any]] = json.load(f)

    if include_disabled:
        return cases

    return [c for c in cases if c.get("enabled", True) is True]

# Backward compatibility alias
BENCHMARK_CASES = load_benchmark_dataset(include_disabled=False)

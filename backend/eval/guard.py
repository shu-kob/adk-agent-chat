"""
Eval Execution Metadata, Version Tracking, and Merge Guard Module
"""

import hashlib
import importlib.metadata
from typing import Dict, Any, List, Optional

DATASET_VERSION = "v2.0.0"
EVALUATOR_VERSION = "v2.0.0"

class MergeGuardViolationError(ValueError):
    """Raised when evaluation records with mismatched environments or parameters are merged."""
    pass

def compute_instruction_hash(instruction: str) -> str:
    """Compute first 12 characters of SHA-256 hash of system instruction."""
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:12]

def get_sdk_versions() -> Dict[str, str]:
    """Retrieve installed versions of relevant Google SDKs."""
    versions = {}
    for pkg, key in [("google-genai", "google_genai"), ("google-adk", "google_adk")]:
        try:
            versions[key] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[key] = "not_installed"
    return versions

def create_trial_record(
    run_id: str,
    trial_index: int,
    case_id: str,
    category: str,
    model_id: str,
    provider_route: str,
    location: Optional[str],
    execution_path: str,
    instruction: str,
    generation_config: Dict[str, Any],
    status: str,
    error_type: Optional[str],
    latency_ms: int,
    score: Optional[float],
    raw_output: str,
    title: Optional[str] = None,
    eval_type: Optional[str] = None,
    prompt_tokens: int = 0,
    candidate_tokens: int = 0,
    cost_usd: float = 0.0,
    reasons: Optional[List[str]] = None,
    assertions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Constructs a fully-typed single trial record meeting SPECIFICATION_ADDENDUM_v1 Phase 1.4 & 2.2 schema.
    """
    is_error = (status == "error")

    record: Dict[str, Any] = {
        "run_id": run_id,
        "trial_index": trial_index,
        "case_id": case_id,
        "category": category,
        "title": title or case_id,
        "eval_type": eval_type,
        "model_id": model_id,
        "provider_route": provider_route,
        "location": location,
        "execution_path": execution_path,
        "instruction_hash": compute_instruction_hash(instruction),
        "dataset_version": DATASET_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "sdk_versions": get_sdk_versions(),
        "generation_config": generation_config,
        "status": status,
        "error_type": error_type,
        "latency_ms": latency_ms,
        "score": None if is_error else score,
        "raw_output": raw_output,
        "prompt_tokens": prompt_tokens,
        "candidate_tokens": candidate_tokens,
        "cost_usd": cost_usd,
        "reasons": reasons or [],
        "assertions": assertions or []
    }
    return record


class MergeGuard:
    """
    Validates that records to be merged into a single comparison matrix
    strictly share identical execution environments and versions.
    """
    GUARD_FIELDS = [
        "provider_route",
        "instruction_hash",
        "dataset_version",
        "evaluator_version"
    ]

    @classmethod
    def validate_mergeable(cls, records: List[Dict[str, Any]]) -> bool:
        if not records:
            return True

        base_record = records[0]
        for idx, rec in enumerate(records[1:], start=1):
            for field in cls.GUARD_FIELDS:
                base_val = base_record.get(field)
                rec_val = rec.get(field)
                if base_val != rec_val:
                    raise MergeGuardViolationError(
                        f"MergeGuard Violation at record {idx}: '{field}' mismatch "
                        f"('{base_val}' vs '{rec_val}'). Cannot merge distinct environments into single matrix."
                    )
        return True

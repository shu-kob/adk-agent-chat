import pytest
import hashlib
from eval.guard import (
    compute_instruction_hash,
    get_sdk_versions,
    create_trial_record,
    MergeGuard,
    MergeGuardViolationError,
    DATASET_VERSION,
    EVALUATOR_VERSION
)

def test_compute_instruction_hash():
    instruction = "You are a helpful assistant."
    expected_hash = hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:12]
    assert compute_instruction_hash(instruction) == expected_hash

def test_get_sdk_versions():
    versions = get_sdk_versions()
    assert isinstance(versions, dict)
    assert "google_genai" in versions
    assert "google_adk" in versions

def test_create_trial_record_success():
    record = create_trial_record(
        run_id="run_20260830_001",
        trial_index=0,
        case_id="struct_01",
        category="structured_output",
        model_id="gemini-2.5-flash",
        provider_route="vertex_ai",
        location="global",
        execution_path="adk",
        instruction="You are a helpful assistant.",
        generation_config={"temperature": 0.0, "seed": 42, "max_output_tokens": 2048},
        status="success",
        error_type=None,
        latency_ms=1234,
        score=1.0,
        raw_output="{\"order_id\": 101}"
    )

    assert record["run_id"] == "run_20260830_001"
    assert record["trial_index"] == 0
    assert record["case_id"] == "struct_01"
    assert record["category"] == "structured_output"
    assert record["model_id"] == "gemini-2.5-flash"
    assert record["provider_route"] == "vertex_ai"
    assert record["location"] == "global"
    assert record["execution_path"] == "adk"
    assert record["instruction_hash"] == compute_instruction_hash("You are a helpful assistant.")
    assert record["dataset_version"] == DATASET_VERSION
    assert record["evaluator_version"] == EVALUATOR_VERSION
    assert record["status"] == "success"
    assert record["error_type"] is None
    assert record["score"] == 1.0
    assert record["raw_output"] == "{\"order_id\": 101}"

def test_create_trial_record_error_score_is_null():
    record = create_trial_record(
        run_id="run_20260830_001",
        trial_index=1,
        case_id="struct_01",
        category="structured_output",
        model_id="gemini-2.5-flash",
        provider_route="vertex_ai",
        location="global",
        execution_path="adk",
        instruction="You are a helpful assistant.",
        generation_config={"temperature": 0.0, "seed": 42, "max_output_tokens": 2048},
        status="error",
        error_type="PermissionDenied",
        latency_ms=45,
        score=0.0, # Error should force score to None
        raw_output=""
    )

    assert record["status"] == "error"
    assert record["error_type"] == "PermissionDenied"
    assert record["score"] is None  # Must be null / None on error

def test_merge_guard_allows_matching_records():
    records = [
        create_trial_record(
            run_id="run_01", trial_index=0, case_id="c1", category="cat1",
            model_id="m1", provider_route="vertex_ai", location="global", execution_path="adk",
            instruction="inst_a", generation_config={}, status="success", error_type=None,
            latency_ms=100, score=1.0, raw_output="ok"
        ),
        create_trial_record(
            run_id="run_01", trial_index=1, case_id="c1", category="cat1",
            model_id="m2", provider_route="vertex_ai", location="global", execution_path="adk",
            instruction="inst_a", generation_config={}, status="success", error_type=None,
            latency_ms=120, score=1.0, raw_output="ok"
        )
    ]
    # Should not raise
    MergeGuard.validate_mergeable(records)

def test_merge_guard_raises_on_different_provider_route():
    records = [
        create_trial_record(
            run_id="run_01", trial_index=0, case_id="c1", category="cat1",
            model_id="m1", provider_route="vertex_ai", location="global", execution_path="adk",
            instruction="inst_a", generation_config={}, status="success", error_type=None,
            latency_ms=100, score=1.0, raw_output="ok"
        ),
        create_trial_record(
            run_id="run_01", trial_index=0, case_id="c1", category="cat1",
            model_id="m2", provider_route="ai_studio", location=None, execution_path="adk",
            instruction="inst_a", generation_config={}, status="success", error_type=None,
            latency_ms=120, score=1.0, raw_output="ok"
        )
    ]
    with pytest.raises(MergeGuardViolationError) as exc_info:
        MergeGuard.validate_mergeable(records)
    assert "provider_route" in str(exc_info.value)

def test_merge_guard_raises_on_different_instruction_hash():
    r1 = create_trial_record(
        run_id="run_01", trial_index=0, case_id="c1", category="cat1",
        model_id="m1", provider_route="vertex_ai", location="global", execution_path="adk",
        instruction="Instruction 1", generation_config={}, status="success", error_type=None,
        latency_ms=100, score=1.0, raw_output="ok"
    )
    r2 = create_trial_record(
        run_id="run_01", trial_index=0, case_id="c1", category="cat1",
        model_id="m1", provider_route="vertex_ai", location="global", execution_path="adk",
        instruction="Instruction 2", generation_config={}, status="success", error_type=None,
        latency_ms=100, score=1.0, raw_output="ok"
    )
    with pytest.raises(MergeGuardViolationError) as exc_info:
        MergeGuard.validate_mergeable([r1, r2])
    assert "instruction_hash" in str(exc_info.value)

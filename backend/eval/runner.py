"""
LLM Evaluation Benchmark Runner (SPECIFICATION_ADDENDUM_v1 Phase 1 Compliant)
Supports multi-trial median aggregation, pre-flight model checks, MergeGuard validation,
strictly deterministic generation parameters, and objective reporting.
"""

import os
import sys
import time
import json
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.dataset import BENCHMARK_CASES
from eval.evaluator import Evaluator
from eval.guard import (
    create_trial_record,
    MergeGuard,
    compute_instruction_hash,
    DATASET_VERSION,
    EVALUATOR_VERSION
)
from eval.precheck import validate_model_availability
from eval.aggregator import (
    aggregate_trials_by_case,
    detect_unstable_cases,
    compute_category_matrix,
    compute_assertion_failure_breakdown,
    generate_markdown_report
)

load_dotenv()

TARGET_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]

DEFAULT_INSTRUCTION = "You are a helpful, friendly, and highly intelligent AI assistant."

# 概算トークン単価 (USD per 1M tokens)
MODEL_PRICING = {
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "default": {"input": 0.15, "output": 0.60}
}

def generate_with_params(
    client: genai.Client,
    model: str,
    prompt: str,
    temperature: float = 0.0,
    seed: Optional[int] = 42,
    max_output_tokens: int = 1024,
    timeout_sec: float = 25.0
) -> Tuple[str, int, int]:
    """
    Calls LLM with strictly controlled generation parameters.
    """
    config_kwargs: Dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens
    }
    if seed is not None:
        config_kwargs["seed"] = seed

    config = types.GenerateContentConfig(**config_kwargs)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.models.generate_content, model=model, contents=prompt, config=config)
        try:
            resp = future.result(timeout=timeout_sec)
            text = resp.text or ""
            prompt_tokens = 0
            candidate_tokens = 0
            if hasattr(resp, "usage_metadata") and resp.usage_metadata:
                prompt_tokens = getattr(resp.usage_metadata, "prompt_token_count", 0) or 0
                candidate_tokens = getattr(resp.usage_metadata, "candidates_token_count", 0) or 0
            return text, prompt_tokens, candidate_tokens
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Generation timed out after {timeout_sec}s")

def calculate_cost(model_name: str, prompt_tokens: int, candidate_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["default"])
    cost = (prompt_tokens / 1_000_000 * pricing["input"]) + (candidate_tokens / 1_000_000 * pricing["output"])
    return round(cost, 6)

def run_benchmark():
    batch_start_dt = datetime.now()
    batch_start_iso = batch_start_dt.isoformat()
    timestamp_str = batch_start_dt.strftime("%Y%m%d_%H%M%S")

    # 1. 実行環境 & パラメータ設定
    provider_route = "vertex_ai" if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true" else "ai_studio"
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip() if provider_route == "vertex_ai" else None
    trials_per_case = int(os.getenv("EVAL_TRIALS", "3"))
    temperature = 0.0
    seed = 42

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    print("=" * 80)
    print("🚀 LLM EVALUATION BENCHMARK: Phase 1 Deterministic Benchmark Runner")
    print(f"📅 Start Time: {batch_start_iso} (Run ID: {timestamp_str})")
    print(f"🌐 Provider Route: {provider_route} (Location: {location})")
    print(f"🔄 Trials per Case: {trials_per_case} (Representative value: Median)")
    print(f"🌡️ Generation Config: temperature={temperature}, seed={seed}")
    print(f"🎯 Target Models: {', '.join(TARGET_MODELS)}")
    print(f"📊 Benchmark Cases: {len(BENCHMARK_CASES)} cases across 5 categories")
    print("=" * 80)

    # 2. Client 初期化
    if provider_route == "vertex_ai":
        if not project:
            print("[ERROR] GOOGLE_CLOUD_PROJECT is not set in environment or .env")
            sys.exit(1)
        client = genai.Client(vertexai=True, project=project, location=location or "global")
    else:
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        if not api_key:
            print("[ERROR] GOOGLE_API_KEY is not set for AI Studio evaluation")
            sys.exit(1)
        client = genai.Client(api_key=api_key)

    # 3. Model 事前疎通チェック (Pre-flight check)
    print("\n🔍 Executing Pre-flight Check for candidate models...")
    valid_models, skipped_models = validate_model_availability(client, TARGET_MODELS)
    for vm in valid_models:
        print(f"  ✅ Model '{vm}' is available and responsive.")
    for sm in skipped_models:
        print(f"  ⚠️ Model '{sm['model_id']}' failed pre-check: {sm['error']}. Skipping.")

    if not valid_models:
        print("[ERROR] No models are available for evaluation.")
        sys.exit(1)

    # 4. ベンチマーク試行ループ
    all_trial_records: List[Dict[str, Any]] = []

    for model_id in valid_models:
        print(f"\n--- 🤖 Evaluating Model: {model_id} ({trials_per_case} trials per case) ---")

        for case_idx, case in enumerate(BENCHMARK_CASES, start=1):
            case_id = case["id"]
            category = case["category"]
            title = case["title"]
            prompt = case["prompt"]
            eval_type = case["eval_type"]
            expected = case["expected"]
            max_tokens = case.get("max_output_tokens", 1024)

            print(f"  [{case_idx:02d}/{len(BENCHMARK_CASES):02d}] ({category:22}) {title:30} ", end="", flush=True)

            case_scores = []
            for trial_idx in range(trials_per_case):
                start_t = time.time()
                response_text = ""
                error_msg = None
                error_type = None
                prompt_tokens = 0
                candidate_tokens = 0

                gen_config = {
                    "temperature": temperature,
                    "seed": seed,
                    "max_output_tokens": max_tokens
                }

                try:
                    response_text, prompt_tokens, candidate_tokens = generate_with_params(
                        client=client,
                        model=model_id,
                        prompt=prompt,
                        temperature=temperature,
                        seed=seed,
                        max_output_tokens=max_tokens,
                        timeout_sec=25.0
                    )
                except Exception as e:
                    error_msg = str(e)
                    error_type = type(e).__name__

                latency_ms = int((time.time() - start_t) * 1000)
                cost_usd = calculate_cost(model_id, prompt_tokens, candidate_tokens)

                if error_msg:
                    score = None
                    reasons = [f"API Execution Error: {error_msg}"]
                    assertions = []
                    status = "error"
                else:
                    score, reasons, assertions = Evaluator.evaluate_detailed(eval_type, response_text, expected)
                    status = "success"
                    case_scores.append(score)

                record = create_trial_record(
                    run_id=timestamp_str,
                    trial_index=trial_idx,
                    case_id=case_id,
                    category=category,
                    title=title,
                    eval_type=eval_type,
                    model_id=model_id,
                    provider_route=provider_route,
                    location=location,
                    execution_path="genai_sdk_direct",
                    instruction=DEFAULT_INSTRUCTION,
                    generation_config=gen_config,
                    status=status,
                    error_type=error_type,
                    latency_ms=latency_ms,
                    score=score,
                    raw_output=response_text,
                    prompt_tokens=prompt_tokens,
                    candidate_tokens=candidate_tokens,
                    cost_usd=cost_usd,
                    reasons=reasons,
                    assertions=assertions
                )
                all_trial_records.append(record)
                time.sleep(0.3)

            # ケースの試行結果表示
            if case_scores:
                median_score = sorted(case_scores)[len(case_scores)//2]
                print(f"✅ Med: {median_score * 100:>3.0f} pts | Scores: {[int(s*100) for s in case_scores]}")
            else:
                print(f"❌ Error in all trials")

    # 5. MergeGuard による整合性検証
    print("\n🛡️ Validating evaluation records with MergeGuard...")
    MergeGuard.validate_mergeable(all_trial_records)
    print("  ✅ All records share strictly identical environment and versions.")

    # 6. 集計計算 (中央値、カテゴリマトリクス、不安定ケース、アサーション失敗内訳)
    categories = sorted(list(set(c["category"] for c in BENCHMARK_CASES)))
    case_summary = aggregate_trials_by_case(all_trial_records)
    unstable_cases = detect_unstable_cases(case_summary)
    category_matrix = compute_category_matrix(case_summary, categories, valid_models)
    assertion_failures = compute_assertion_failure_breakdown(all_trial_records)

    batch_end_dt = datetime.now()
    batch_end_iso = batch_end_dt.isoformat()
    total_batch_duration = (batch_end_dt - batch_start_dt).total_seconds()
    total_batch_cost = sum(r["cost_usd"] for r in all_trial_records)

    batch_meta = {
        "run_id": timestamp_str,
        "started_at": batch_start_iso,
        "completed_at": batch_end_iso,
        "duration_sec": round(total_batch_duration, 2),
        "total_cost_usd": round(total_batch_cost, 6),
        "provider_route": provider_route,
        "location": location,
        "trials_per_case": trials_per_case,
        "temperature": temperature,
        "seed": seed,
        "dataset_version": DATASET_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "models": valid_models,
        "skipped_models": skipped_models
    }

    # 7. レポート生成 & 保存
    report_text = generate_markdown_report(
        batch_meta,
        category_matrix,
        unstable_cases,
        assertion_failures=assertion_failures
    )

    report_path = os.path.join(results_dir, f"eval_report_phase1_{timestamp_str}.md")
    latest_report_path = os.path.join(results_dir, "eval_report_latest.md")
    raw_json_path = os.path.join(results_dir, f"eval_raw_phase1_{timestamp_str}.json")

    json_payload = {
        "batch_meta": batch_meta,
        "records": all_trial_records,
        "case_summary": {f"{k[0]}__{k[1]}": v for k, v in case_summary.items()},
        "category_matrix": category_matrix,
        "unstable_cases": unstable_cases
    }

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(latest_report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(raw_json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("📈 FINAL SUMMARY MATRIX (Median Scores with Sample Sizes)")
    print(f"⏱️ Duration: {total_batch_duration:.2f}s | 💰 Cost: ${total_batch_cost:.5f}")
    print("=" * 80)
    print(report_text)
    print("=" * 80)
    print(f"📁 Reports saved to:\n  - {report_path}\n  - {raw_json_path}")

if __name__ == "__main__":
    run_benchmark()

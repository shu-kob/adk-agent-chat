"""
LLM ベンチマーク評価実行ランナー (backend/eval/runner.py)

【役割】
- SPECIFICATION_ADDENDUM_v1 Phase 1 & 2 準拠のバッチ評価を実行する。
- 事前疎通チェック (validate_model_availability)、決定論的パラメータ固定 (temp=0.0, seed=42, max_output_tokens)、
  複数回試行 (EVAL_TRIALS, 既定3回)、アサーション単位採点 (Evaluator.evaluate_detailed)、
  マージガード検証 (MergeGuard)、中央値集計、アサーション失敗内訳集計、レポート自動生成を一括制御する。
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

# backend ルートをインポートパスに追加 (eval 配下からの直接実行に対応)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 評価データセット、採点エンジン、メタデータガード、集計モジュールの参照
from eval.dataset import BENCHMARK_CASES  # 外部 JSON からロードされた有効評価ケース一覧
from eval.evaluator import Evaluator      # 決定論的アサーション評価エンジン
from eval.guard import (
    create_trial_record,
    MergeGuard,
    compute_instruction_hash,
    DATASET_VERSION,
    EVALUATOR_VERSION
)
from eval.precheck import validate_model_availability  # 事前疎通チェック
from eval.aggregator import (
    aggregate_trials_by_case,
    detect_unstable_cases,
    compute_category_matrix,
    compute_assertion_failure_breakdown,
    compute_coverage_metrics,
    compute_common_case_matrix,
    compute_truncation_metrics,
    generate_markdown_report
)

# .env ファイルの環境変数をロード
load_dotenv()

# ==============================================================================
# 評価対象モデルおよび定数定義
# ==============================================================================
# ベンチマークで比較評価するターゲットモデル一覧
TARGET_MODELS: List[str] = [
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
]

# 共通システムインストラクション
DEFAULT_INSTRUCTION: str = "You are a helpful, friendly, and highly intelligent AI assistant."

# 概算トークン単価 (USD per 1M tokens) - 実費トラッキング用
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-3.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-3.7-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
    "default": {"input": 0.15, "output": 0.60}
}

def generate_with_params(
    client: genai.Client,
    model: str,
    prompt: str,
    temperature: float = 0.0,
    seed: int = 42,
    max_output_tokens: int = 4096,
    thinking_budget: Optional[int] = None,
    timeout_sec: float = 30.0
) -> Tuple[str, int, int, Optional[str], Optional[int], Optional[Dict[str, Any]]]:
    """
    決定論的パラメータを厳格に固定して Gemini モデルを呼び出し、
    生成テキスト、消費トークン数、停止理由、思考トークン数、および usage 生データを取得する。
    
    :param client: google.genai.Client インスタンス
    :param model: 呼び出し対象モデル名
    :param prompt: 入力プロンプト
    :param temperature: 生成温度 (決定論的評価のため 0.0 固定)
    :param seed: 乱数シード値 (42 固定)
    :param max_output_tokens: 最大出力トークン数 (既定 4096)
    :param thinking_budget: 思考予算トークン数 (None の場合はモデル既定)
    :param timeout_sec: タイムアウト秒数
    :return: (生成テキスト, 入力トークン数, 出力トークン数, finish_reason, thinking_tokens, usage_raw)
    :raises TimeoutError: 指定時間内に応答が返らない場合
    """
    config_kwargs: Dict[str, Any] = {
        "temperature": temperature,
        "seed": seed,
        "max_output_tokens": max_output_tokens,
        "system_instruction": DEFAULT_INSTRUCTION
    }
    if thinking_budget is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

    config = types.GenerateContentConfig(**config_kwargs)

    def _call():
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )
        text = response.text if response.text else ""
        prompt_tokens = 0
        candidate_tokens = 0
        thinking_tokens = None
        usage_raw = None
        finish_reason = None

        # finish_reason の取得 (SDK の candidate から加工せず記録)
        if response.candidates and len(response.candidates) > 0:
            c = response.candidates[0]
            if hasattr(c, "finish_reason") and c.finish_reason is not None:
                # enum の場合は .name または 文字列表現を加工せず取得
                finish_reason = getattr(c.finish_reason, "name", str(c.finish_reason))

        # usage_metadata の取得
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            prompt_tokens = getattr(um, "prompt_token_count", 0) or 0
            candidate_tokens = getattr(um, "candidates_token_count", 0) or 0
            # 思考トークン (thoughts_token_count) の取得
            thinking_tokens = getattr(um, "thoughts_token_count", None)

            # usage_raw として辞書化して保存
            if hasattr(um, "model_dump"):
                try:
                    usage_raw = um.model_dump()
                except Exception:
                    usage_raw = None
            elif hasattr(um, "to_dict"):
                try:
                    usage_raw = um.to_dict()
                except Exception:
                    usage_raw = None

        return text, prompt_tokens, candidate_tokens, finish_reason, thinking_tokens, usage_raw

    # タイムアウト付きスレッドプール実行
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Generation timed out after {timeout_sec}s for model {model}")

# リトライ対象エラー（429 レート制限、503 一時不可、タイムアウト、接続切断）
RETRYABLE_ERROR_TYPES = (
    "ResourceExhausted",
    "RESOURCE_EXHAUSTED",
    "ServiceUnavailable",
    "UNAVAILABLE",
    "TimeoutError",
    "DeadlineExceeded",
    "DEADLINE_EXCEEDED",
    "ConnectionError",
    "APIConnectionError"
)

# リトライ対象外エラー（400番台の確定エラー等）
NON_RETRYABLE_ERROR_TYPES = (
    "InvalidArgument",
    "INVALID_ARGUMENT",
    "PermissionDenied",
    "PERMISSION_DENIED",
    "Unauthenticated",
    "UNAUTHENTICATED",
    "NotFound",
    "NOT_FOUND",
    "ValueError"
)

def is_retryable_error(exc: Exception) -> bool:
    """
    発生した例外が一時的なレート制限やネットワーク障害等、リトライ対象であるかを判定する。
    
    :param exc: 検査対象の例外
    :return: リトライすべき場合 True、即時失敗とすべき場合 False
    """
    exc_type_name = type(exc).__name__
    exc_str = str(exc)

    # 明示的な非リトライ対象の判定
    for non_ret in NON_RETRYABLE_ERROR_TYPES:
        if non_ret in exc_type_name or non_ret in exc_str:
            return False

    # リトライ対象の判定
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True

    for ret in RETRYABLE_ERROR_TYPES:
        if ret in exc_type_name or ret in exc_str or "429" in exc_str or "503" in exc_str:
            return True

    return False

def execute_call_with_retry(
    call_fn: Any,
    max_retries: Optional[int] = None,
    base_delay_sec: Optional[float] = None,
    backoff_factor: float = 2.0
) -> Tuple[Any, int]:
    """
    指数バックオフとジッタを用いて、指定された API 呼び出し関数を実行する。
    
    :param call_fn: 実行する引数なし callable
    :param max_retries: 最大リトライ回数 (環境変数 EVAL_RETRY_MAX または既定 5)
    :param base_delay_sec: 初回待機秒数 (環境変数 EVAL_RETRY_BASE_SEC または既定 2.0)
    :param backoff_factor: バックオフ乗数 (既定 2.0)
    :return: (関数実行結果, 実施したリトライ回数)
    :raises: リトライ上限超過時または非リトライ対象例外発生時
    """
    import random
    if max_retries is None:
        max_retries = int(os.getenv("EVAL_RETRY_MAX", "5"))
    if base_delay_sec is None:
        base_delay_sec = float(os.getenv("EVAL_RETRY_BASE_SEC", "2.0"))

    retry_count = 0
    while True:
        try:
            res = call_fn()
            return res, retry_count
        except Exception as e:
            if not is_retryable_error(e) or retry_count >= max_retries:
                raise e
            
            retry_count += 1
            jitter = random.uniform(0.1, 0.5)
            delay = (base_delay_sec * (backoff_factor ** (retry_count - 1))) + jitter
            time.sleep(delay)

def calculate_cost(model_name: str, prompt_tokens: int, candidate_tokens: int) -> float:
    """
    消費トークン数からドル建ての概算コスト (USD) を計算する。
    
    :param model_name: モデル名
    :param prompt_tokens: 入力トークン数
    :param candidate_tokens: 出力トークン数
    :return: 概算コスト (USD)
    """
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["default"])
    cost = (prompt_tokens / 1_000_000 * pricing["input"]) + (candidate_tokens / 1_000_000 * pricing["output"])
    return round(cost, 8)

def main():
    """
    LLM ベンチマーク評価のメイン実行エントリーポイント
    """
    print("=" * 70)
    print(f"🚀 Starting LLM Benchmark Evaluation Suite (Phase 2 Dataset Expansion)")
    print(f"   Dataset Version: {DATASET_VERSION} | Evaluator Version: {EVALUATOR_VERSION}")
    print("=" * 70)

    # 1. 認証と GenAI クライアント初期化
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("true", "1", "yes")
    api_key = os.getenv("GOOGLE_API_KEY", "").strip().strip('"\'')
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip().strip('"\'')
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip().strip('"\'')

    if use_vertex:
        provider_route = "vertex_ai"
        client = genai.Client(vertexai=True, project=project, location=location)
        print(f"📡 Provider: Google Cloud Vertex AI (Project: {project}, Location: {location})")
    elif api_key:
        provider_route = "ai_studio"
        location = None
        client = genai.Client(api_key=api_key)
        print("📡 Provider: Google AI Studio (API Key)")
    else:
        print("❌ Error: No authentication provided. Set GOOGLE_API_KEY or configure Vertex AI ADC.")
        sys.exit(1)

    # 2. 事前疎通チェック (Pre-flight check)
    print("\n🔍 Running pre-flight model availability check...")
    valid_models, skipped_models = validate_model_availability(client, TARGET_MODELS)
    print(f"  ✅ Available models: {valid_models}")
    if skipped_models:
        for sk in skipped_models:
            print(f"  ⚠️ Skipped model: {sk['model_id']} (Reason: {sk['error']})")

    if not valid_models:
        print("❌ Error: No valid models available to evaluate. Aborting.")
        sys.exit(1)

    # 3. 実行パラメータおよび試行回数の設定
    trials_per_case = int(os.getenv("EVAL_TRIALS", "3"))  # 既定 3 回試行
    temperature = 0.0                                    # 決定論的固定
    seed = 42                                            # 乱数シード固定
    instruction_hash = compute_instruction_hash(DEFAULT_INSTRUCTION)

    # max_output_tokens の既定値を 4096 に引き上げ (SPECIFICATION_ADDENDUM_v6 §1.2)
    default_max_output_tokens = int(os.getenv("EVAL_MAX_OUTPUT_TOKENS", "4096"))
    thinking_budget_env = os.getenv("EVAL_THINKING_BUDGET")
    thinking_budget = int(thinking_budget_env) if (thinking_budget_env is not None and thinking_budget_env.strip() != "") else None

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_start_dt = datetime.now()
    batch_start_iso = batch_start_dt.isoformat()

    print(f"\n⚙️ Parameters: Trials={trials_per_case} | Temp={temperature} | Seed={seed} | MaxOutputTokens={default_max_output_tokens} | ThinkingBudget={thinking_budget}")
    print(f"📁 Benchmark Cases: {len(BENCHMARK_CASES)} enabled cases loaded from JSON")

    # 4. 全ケース × 全モデル × 全試行のループ実行
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
            # データセット側で個別に大きな値が指定されている場合はそれを尊重し、最低でも default_max_output_tokens を保証
            max_tokens = max(case.get("max_output_tokens", 0), default_max_output_tokens)

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
                    "max_output_tokens": max_tokens,
                    "thinking_budget": thinking_budget
                }

                finish_reason = None
                thinking_tokens = None
                usage_raw = None
                truncated = None
                truncation_type = None

                retry_cnt = 0
                try:
                    def _do_generate():
                        return generate_with_params(
                            client=client,
                            model=model_id,
                            prompt=prompt,
                            temperature=temperature,
                            seed=seed,
                            max_output_tokens=max_tokens,
                            thinking_budget=thinking_budget,
                            timeout_sec=30.0
                        )

                    (response_text, prompt_tokens, candidate_tokens, finish_reason, thinking_tokens, usage_raw), retry_cnt = execute_call_with_retry(_do_generate)
                except Exception as e:
                    error_msg = str(e)
                    error_type = type(e).__name__

                # truncated & truncation_type の判定条件 (SPECIFICATION_ADDENDUM_v6 §4.2):
                # - finish_reason がトークン上限到達 (MAX_TOKENS / MAX_OUTPUT_TOKENS / LENGTH) の場合:
                #   truncated = True
                #   - thinking_tokens が存在し、かつ thinking_tokens > candidate_tokens の場合:
                #       truncation_type = "thinking_dominant" (思考トークンが可視出力を上回り、予算を圧迫して打ち切られた)
                #   - thinking_tokens が None または thinking_tokens <= candidate_tokens の場合:
                #       truncation_type = "output_dominant" (可視出力そのものが上限付近に達して打ち切られた)
                # - finish_reason が STOP / SAFETY 等の場合:
                #   truncated = False
                #   truncation_type = None
                # - finish_reason が取得できない (None) の場合:
                #   truncated = None
                #   truncation_type = "unknown"
                if finish_reason is not None:
                    if finish_reason in ("MAX_TOKENS", "MAX_OUTPUT_TOKENS", "LENGTH"):
                        truncated = True
                        if thinking_tokens is not None and thinking_tokens > candidate_tokens:
                            truncation_type = "thinking_dominant"
                        else:
                            truncation_type = "output_dominant"
                    else:
                        truncated = False
                        truncation_type = None
                else:
                    truncated = None
                    truncation_type = "unknown"

                # スロットリング (呼び出し間隔制御)
                request_interval = float(os.getenv("EVAL_REQUEST_INTERVAL_SEC", "1.0"))
                if request_interval > 0:
                    time.sleep(request_interval)

                latency_ms = int((time.time() - start_t) * 1000)
                cost_usd = calculate_cost(model_id, prompt_tokens, candidate_tokens)

                if error_msg:
                    score = None
                    reasons = [f"API Execution Error: {error_msg}"]
                    assertions = []
                    status = "error"
                else:
                    # アサーション単位の詳細判定
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
                    retry_count=retry_cnt,
                    finish_reason=finish_reason,
                    truncated=truncated,
                    truncation_type=truncation_type,
                    thinking_tokens=thinking_tokens,
                    usage_raw=usage_raw,
                    reasons=reasons,
                    assertions=assertions
                )
                all_trial_records.append(record)
                time.sleep(0.3)

            # ケースの試行結果表示 (中央値)
            if case_scores:
                median_score = sorted(case_scores)[len(case_scores)//2]
                print(f"✅ Med: {median_score * 100:>3.0f} pts | Scores: {[int(s*100) for s in case_scores]}")
            else:
                print(f"❌ Error in all trials")

    # 5. MergeGuard による整合性検証
    print("\n🛡️ Validating evaluation records with MergeGuard...")
    MergeGuard.validate_mergeable(all_trial_records)
    print("  ✅ All records share strictly identical environment and versions.")

    # 6. 集計計算 (中央値、カバレッジ、共通マトリクス、失敗分布、不安定ケース、アサーション失敗内訳)
    categories = sorted(list(set(c["category"] for c in BENCHMARK_CASES)))
    case_summary = aggregate_trials_by_case(all_trial_records)
    unstable_cases = detect_unstable_cases(case_summary)
    category_matrix = compute_category_matrix(case_summary, categories, valid_models)
    assertion_failures = compute_assertion_failure_breakdown(all_trial_records)
    truncation_metrics = compute_truncation_metrics(all_trial_records, valid_models)

    # v4: カバレッジおよび共通ケースマトリクスの集計
    all_cases_dict = [{"case_id": c["id"], "category": c["category"]} for c in BENCHMARK_CASES]
    coverage_metrics = compute_coverage_metrics(case_summary, all_cases_dict, valid_models)
    common_case_matrix, common_cases_count, excluded_cases_count = compute_common_case_matrix(
        case_summary, all_cases_dict, valid_models
    )

    # 未測定ケース一覧の収集
    unmeasured_cases = []
    for (cid, mid), info in case_summary.items():
        if info.get("median_score") is None:
            unmeasured_cases.append({
                "case_id": cid,
                "category": info.get("category"),
                "model_id": mid,
                "error_type": info.get("error_type", "UnknownError")
            })

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
        batch_meta=batch_meta,
        category_matrix=category_matrix,
        unstable_cases=unstable_cases,
        assertion_failures=assertion_failures,
        coverage_metrics=coverage_metrics,
        common_case_matrix=common_case_matrix,
        common_cases_count=common_cases_count,
        excluded_cases_count=excluded_cases_count,
        unmeasured_cases=unmeasured_cases,
        truncation_metrics=truncation_metrics
    )

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    report_path = os.path.join(results_dir, f"eval_report_phase1_{timestamp_str}.md")
    latest_report_path = os.path.join(results_dir, "eval_report_latest.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(latest_report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 8. ローデータ JSON 保存
    raw_output_path = os.path.join(results_dir, f"eval_raw_phase1_{timestamp_str}.json")
    raw_payload = {
        "batch_meta": batch_meta,
        "coverage_metrics": coverage_metrics,
        "common_case_matrix": common_case_matrix,
        "case_summary": {f"{k[0]}::{k[1]}": v for k, v in case_summary.items()},
        "category_matrix": category_matrix,
        "assertion_failures": assertion_failures,
        "unstable_cases": unstable_cases,
        "unmeasured_cases": unmeasured_cases,
        "truncation_metrics": truncation_metrics,
        "records": all_trial_records
    }
    with open(raw_output_path, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"🎉 Evaluation Complete! ({total_batch_duration:.1f}s, Total Cost: ${total_batch_cost:.6f})")
    print(f"📄 Report written to: {report_path}")
    print(f"📄 Latest Report at: {latest_report_path}")
    print(f"💾 Raw Data saved to: {raw_output_path}")
    print("=" * 70)
    print("\n" + report_text)

if __name__ == "__main__":
    main()

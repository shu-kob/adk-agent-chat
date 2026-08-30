"""
LLM Evaluation Benchmark Runner (Vertex AI Global - Gemini 3 Series)
Vertex AI (global) 経由で Gemini 3 世代モデルをベンチマーク評価する
"""

import os
import sys
import time
import json
import csv
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.dataset import BENCHMARK_CASES
from eval.evaluator import Evaluator

load_dotenv()

TARGET_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
]

# 概算トークン単価 (USD per 1M tokens) - 参考値
MODEL_PRICING = {
    "gemini-3.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-3.7-flash": {"input": 0.15, "output": 0.60},
    "gemini-3-flash-preview": {"input": 0.15, "output": 0.60},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
    "default": {"input": 0.15, "output": 0.60}
}

def generate_with_timeout(
    client: genai.Client,
    model: str,
    prompt: str,
    timeout_sec: float = 20.0
) -> Tuple[str, int, int]:
    """
    LLM 呼び出しを行い、(テキスト応答, 入力トークン数, 出力トークン数) を返す
    """
    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=2048,
    )
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

    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip()

    if not project:
        print("[ERROR] GOOGLE_CLOUD_PROJECT is not set in environment or .env")
        sys.exit(1)

    client = genai.Client(vertexai=True, project=project, location=location)

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    print("=" * 80)
    print("🚀 LLM EVALUATION BENCHMARK: Vertex AI (Global) - Gemini 3 Series Comparison")
    print(f"📅 Start Time: {batch_start_iso} (Run ID: {timestamp_str})")
    print(f"🌐 Backend: Google Cloud Vertex AI (Location: {location})")
    print(f"🎯 Target Models ({len(TARGET_MODELS)}): {', '.join(TARGET_MODELS)}")
    print(f"📊 Benchmark Cases ({len(BENCHMARK_CASES)}): across 5 categories")
    print("=" * 80)

    # 1行1レコードの行指向データ配列 (N候補モデルへの拡張対応)
    flat_records: List[Dict[str, Any]] = []
    
    # 階層型辞書 (既存互換)
    all_runs: Dict[str, Dict[str, Any]] = {}
    model_stats: Dict[str, Dict[str, Any]] = {}

    for model_name in TARGET_MODELS:
        print(f"\n--- 🤖 Evaluating Model on Vertex AI: {model_name} ---")
        all_runs[model_name] = {}
        total_time = 0.0
        total_score = 0.0
        total_cases = len(BENCHMARK_CASES)
        success_cases = 0
        total_prompt_tokens = 0
        total_candidate_tokens = 0

        for idx, case in enumerate(BENCHMARK_CASES, 1):
            case_id = case["id"]
            category = case["category"]
            title = case["title"]
            prompt = case["prompt"]
            eval_type = case["eval_type"]
            expected = case["expected"]

            print(f"  [{idx:02d}/{total_cases:02d}] ({category:22}) {title:30} ... ", end="", flush=True)

            case_start_t = time.time()
            response_text = ""
            error_msg = None
            prompt_tokens = 0
            candidate_tokens = 0

            try:
                response_text, prompt_tokens, candidate_tokens = generate_with_timeout(
                    client, model_name, prompt, timeout_sec=20.0
                )
            except Exception as e:
                error_msg = str(e)

            latency = time.time() - case_start_t
            total_time += latency
            total_prompt_tokens += prompt_tokens
            total_candidate_tokens += candidate_tokens
            cost_usd = calculate_cost(model_name, prompt_tokens, candidate_tokens)

            if error_msg:
                score = 0.0
                reasons = [f"Vertex AI Error: {error_msg}"]
                print(f"❌ 0 pts ({latency:.2f}s) - {error_msg[:35]}")
            else:
                score, reasons = Evaluator.evaluate(eval_type, response_text, expected)
                total_score += score
                success_cases += 1
                print(f"✅ {score * 100:>3.0f} pts ({latency:.2f}s)")

            case_record = {
                "run_id": timestamp_str,
                "case_id": case_id,
                "category": category,
                "title": title,
                "model": model_name,
                "eval_type": eval_type,
                "score": round(score, 3),
                "latency_sec": round(latency, 3),
                "prompt_tokens": prompt_tokens,
                "candidate_tokens": candidate_tokens,
                "cost_usd": cost_usd,
                "reasons": reasons,
                "response": response_text,
                "error": error_msg,
                "evaluated_at": datetime.now().isoformat()
            }

            flat_records.append(case_record)
            all_runs[model_name][case_id] = case_record
            time.sleep(0.5)

        avg_score = (total_score / total_cases) * 100
        avg_latency = total_time / total_cases
        total_model_cost = calculate_cost(model_name, total_prompt_tokens, total_candidate_tokens)

        model_stats[model_name] = {
            "avg_score": round(avg_score, 1),
            "avg_latency": round(avg_latency, 2),
            "total_time": round(total_time, 2),
            "success_cases": success_cases,
            "total_prompt_tokens": total_prompt_tokens,
            "total_candidate_tokens": total_candidate_tokens,
            "estimated_cost_usd": total_model_cost
        }
        print(f"  🏁 {model_name} Finished: Avg Score = {avg_score:.1f}% | Avg Latency = {avg_latency:.2f}s | Cost ≈ ${total_model_cost:.5f}")

    batch_end_dt = datetime.now()
    batch_end_iso = batch_end_dt.isoformat()
    total_batch_duration = (batch_end_dt - batch_start_dt).total_seconds()
    total_batch_cost = sum(st["estimated_cost_usd"] for st in model_stats.values())

    # -------------------------------------------------------------
    # マトリクス集計 (カテゴリ別)
    # -------------------------------------------------------------
    categories = sorted(list(set(c["category"] for c in BENCHMARK_CASES)))
    cat_matrix: Dict[str, Dict[str, float]] = {cat: {} for cat in categories}
    for cat in categories:
        cat_cases = [c["id"] for c in BENCHMARK_CASES if c["category"] == cat]
        for m in TARGET_MODELS:
            scores = [all_runs[m][cid]["score"] * 100 for cid in cat_cases if cid in all_runs[m]]
            cat_matrix[cat][m] = round(sum(scores) / len(scores), 1) if scores else 0.0

    # -------------------------------------------------------------
    # レポート作成 (Markdown & JSON)
    # -------------------------------------------------------------
    report_lines = []
    report_lines.append("# 📊 LLM Evaluation Benchmark Report: Vertex AI (Global) - Gemini 3 Series\n")
    report_lines.append(f"- **Run ID**: `{timestamp_str}`")
    report_lines.append(f"- **Batch Start Time**: `{batch_start_iso}`")
    report_lines.append(f"- **Batch Completed Time**: `{batch_end_iso}`")
    report_lines.append(f"- **Total Duration**: **{total_batch_duration:.2f}s** ({total_batch_duration/60:.2f} min)")
    report_lines.append(f"- **Estimated Total Cost**: **${total_batch_cost:.5f}**")
    report_lines.append(f"- **Backend Engine**: Google Cloud Vertex AI (`location={location}`)")
    report_lines.append(f"- **Total Benchmark Cases**: {len(BENCHMARK_CASES)} cases")
    report_lines.append(f"- **Target Models**: {', '.join(TARGET_MODELS)}\n")
    report_lines.append("## 1. Category-wise Score Matrix (%)\n")

    header = "| Category | " + " | ".join([f"`{m}`" for m in TARGET_MODELS]) + " |"
    sep = "|:---| " + " | ".join([":---:" for _ in TARGET_MODELS]) + " |"
    report_lines.append(header)
    report_lines.append(sep)

    for cat in categories:
        row = f"| **`{cat}`** | " + " | ".join([f"{cat_matrix[cat][m]:.1f}%" for m in TARGET_MODELS]) + " |"
        report_lines.append(row)

    total_row = "| **🔥 Overall Average** | " + " | ".join([f"**{model_stats[m]['avg_score']:.1f}%**" for m in TARGET_MODELS]) + " |"
    report_lines.append(total_row)
    latency_row = "| **⏱️ Avg Latency** | " + " | ".join([f"{model_stats[m]['avg_latency']:.2f}s" for m in TARGET_MODELS]) + " |"
    report_lines.append(latency_row)
    cost_row = "| **💰 Estimated Cost** | " + " | ".join([f"${model_stats[m]['estimated_cost_usd']:.5f}" for m in TARGET_MODELS]) + " |"
    report_lines.append(cost_row)

    report_lines.append("\n## 2. Detailed Case Breakdown\n")
    for case in BENCHMARK_CASES:
        cid = case["id"]
        report_lines.append(f"### Case: `{cid}` - {case['title']} (`{case['category']}`)")
        report_lines.append(f"**Prompt Snippet**: `{case['prompt'][:90]}...`\n")
        report_lines.append("| Model | Score | Latency | Tokens (In/Out) | Est. Cost | Evaluation Details |")
        report_lines.append("|:---|:---:|:---:|:---:|:---:|:---|")
        for m in TARGET_MODELS:
            if cid in all_runs[m]:
                res = all_runs[m][cid]
                reasons_str = "<br>".join(res["reasons"])
                tokens_str = f"{res.get('prompt_tokens', 0)} / {res.get('candidate_tokens', 0)}"
                cost_str = f"${res.get('cost_usd', 0.0):.5f}"
                report_lines.append(f"| `{m}` | {res['score']*100:.0f}% | {res['latency_sec']}s | {tokens_str} | {cost_str} | {reasons_str} |")
        report_lines.append("")

    report_text = "\n".join(report_lines)

    report_path = os.path.join(results_dir, f"eval_report_gemini3_{timestamp_str}.md")
    latest_report_path = os.path.join(results_dir, "eval_report_latest.md")
    raw_json_path = os.path.join(results_dir, f"eval_raw_gemini3_{timestamp_str}.json")

    # JSON 出力: 行指向 records + 階層型 runs + matrix + stats + batch_meta
    json_payload = {
        "batch_meta": {
            "run_id": timestamp_str,
            "started_at": batch_start_iso,
            "completed_at": batch_end_iso,
            "duration_sec": round(total_batch_duration, 2),
            "total_cost_usd": round(total_batch_cost, 6),
            "model_count": len(TARGET_MODELS),
            "case_count": len(BENCHMARK_CASES)
        },
        "records": flat_records,
        "runs": all_runs,
        "matrix": cat_matrix,
        "stats": model_stats
    }

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(latest_report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(raw_json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("📈 FINAL SUMMARY MATRIX & EXECUTION TIME")
    print(f"⏱️ Total Duration: {total_batch_duration:.2f}s | 💰 Total Est. Cost: ${total_batch_cost:.5f}")
    print("=" * 80)
    print(header)
    print(sep)
    for cat in categories:
        print(f"| {cat:22} | " + " | ".join([f"{cat_matrix[cat][m]:>22.1f}%" for m in TARGET_MODELS]) + " |")
    print(total_row)
    print(latency_row)
    print(cost_row)
    print("=" * 80)
    print(f"📁 Reports saved to:\n  - {report_path}\n  - {raw_json_path}")

if __name__ == "__main__":
    run_benchmark()

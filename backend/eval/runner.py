"""
LLM Evaluation Benchmark Runner (Robust REST Client)
複数世代のGeminiモデルに対してバッチ推論・採点・マトリクス集計を実行する
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, Any, List
import httpx
from dotenv import load_dotenv

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.dataset import BENCHMARK_CASES
from eval.evaluator import Evaluator

load_dotenv()

# ユーザー指定のモデル + 比較検証用モデル
TARGET_MODELS = [
    # ユーザー指定モデル
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.1-pro-preview",
    # 比較・実証補完モデル (同世代・後継世代)
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]

def query_gemini_rest(model: str, prompt: str, api_key: str, timeout: float = 12.0) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        }
    }
    # 3.7-flash のような thinking モデル用
    if "3.7" in model:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""
        elif r.status_code == 429:
            raise RuntimeError("429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit)")
        elif r.status_code == 503:
            raise RuntimeError("503 UNAVAILABLE (Model High Demand / Capacity Limit)")
        else:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")

def run_benchmark():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY is not set.")
        sys.exit(1)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    print("=" * 80)
    print("🚀 LLM EVALUATION BENCHMARK: Multi-Generation Comparison")
    print(f"📅 Timestamp: {timestamp_str}")
    print(f"🎯 Target Models ({len(TARGET_MODELS)}): {', '.join(TARGET_MODELS)}")
    print(f"📊 Benchmark Cases: {len(BENCHMARK_CASES)} cases across 5 categories")
    print("=" * 80)

    all_runs: Dict[str, Dict[str, Any]] = {}
    model_stats: Dict[str, Dict[str, Any]] = {}

    for model_name in TARGET_MODELS:
        print(f"\n--- 🤖 Evaluating Model: {model_name} ---")
        all_runs[model_name] = {}
        total_time = 0.0
        total_score = 0.0
        total_cases = len(BENCHMARK_CASES)
        success_cases = 0

        for idx, case in enumerate(BENCHMARK_CASES, 1):
            case_id = case["id"]
            category = case["category"]
            title = case["title"]
            prompt = case["prompt"]
            eval_type = case["eval_type"]
            expected = case["expected"]

            print(f"  [{idx:02d}/{total_cases:02d}] ({category:22}) {title:30} ... ", end="", flush=True)

            start_t = time.time()
            response_text = ""
            error_msg = None
            try:
                response_text = query_gemini_rest(model_name, prompt, api_key, timeout=12.0)
            except Exception as e:
                error_msg = str(e)

            latency = time.time() - start_t
            total_time += latency

            if error_msg:
                score = 0.0
                reasons = [f"API Error: {error_msg}"]
                print(f"❌ 0 pts ({latency:.2f}s) - {error_msg[:35]}")
            else:
                score, reasons = Evaluator.evaluate(eval_type, response_text, expected)
                total_score += score
                success_cases += 1
                print(f"✅ {score * 100:>3.0f} pts ({latency:.2f}s)")

            all_runs[model_name][case_id] = {
                "id": case_id,
                "category": category,
                "title": title,
                "eval_type": eval_type,
                "latency_sec": round(latency, 3),
                "score": round(score, 3),
                "reasons": reasons,
                "response": response_text,
                "error": error_msg
            }
            time.sleep(0.3)

        avg_score = (total_score / total_cases) * 100
        avg_latency = total_time / total_cases
        model_stats[model_name] = {
            "avg_score": round(avg_score, 1),
            "avg_latency": round(avg_latency, 2),
            "total_time": round(total_time, 2),
            "success_cases": success_cases
        }
        print(f"  🏁 {model_name} Finished: Avg Score = {avg_score:.1f}% | Avg Latency = {avg_latency:.2f}s (Success: {success_cases}/{total_cases})")

    # -------------------------------------------------------------
    # マトリクス集計 (カテゴリ別)
    # -------------------------------------------------------------
    categories = sorted(list(set(c["category"] for c in BENCHMARK_CASES)))
    cat_matrix: Dict[str, Dict[str, float]] = {cat: {} for cat in categories}
    for cat in categories:
        cat_cases = [c["id"] for c in BENCHMARK_CASES if c["category"] == cat]
        for m in TARGET_MODELS:
            scores = [all_runs[m][cid]["score"] * 100 for cid in cat_cases]
            cat_matrix[cat][m] = round(sum(scores) / len(scores), 1) if scores else 0.0

    # -------------------------------------------------------------
    # レポート作成 (Markdown & JSON)
    # -------------------------------------------------------------
    report_lines = []
    report_lines.append("# 📊 LLM Evaluation Benchmark Report: Multi-Generation Comparison\n")
    report_lines.append(f"- **Execution Timestamp**: {timestamp_str}")
    report_lines.append(f"- **Total Benchmark Cases**: {len(BENCHMARK_CASES)} cases")
    report_lines.append(f"- **Evaluated Models**: {', '.join(TARGET_MODELS)}\n")
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

    report_lines.append("\n## 2. Detailed Case Breakdown & Insights\n")
    for case in BENCHMARK_CASES:
        cid = case["id"]
        report_lines.append(f"### Case: `{cid}` - {case['title']} (`{case['category']}`)")
        report_lines.append(f"**Prompt Snippet**: `{case['prompt'][:90]}...`\n")
        report_lines.append("| Model | Score | Latency | Evaluation Details |")
        report_lines.append("|:---|:---:|:---:|:---|")
        for m in TARGET_MODELS:
            res = all_runs[m][cid]
            reasons_str = "<br>".join(res["reasons"])
            report_lines.append(f"| `{m}` | {res['score']*100:.0f}% | {res['latency_sec']}s | {reasons_str} |")
        report_lines.append("")

    report_text = "\n".join(report_lines)

    report_path = os.path.join(results_dir, f"eval_report_{timestamp_str}.md")
    latest_report_path = os.path.join(results_dir, "eval_report_latest.md")
    raw_json_path = os.path.join(results_dir, f"eval_raw_{timestamp_str}.json")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(latest_report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(raw_json_path, "w", encoding="utf-8") as f:
        json.dump({"runs": all_runs, "matrix": cat_matrix, "stats": model_stats}, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("📈 FINAL SUMMARY MATRIX")
    print("=" * 80)
    print(header)
    print(sep)
    for cat in categories:
        print(f"| {cat:22} | " + " | ".join([f"{cat_matrix[cat][m]:>20.1f}%" for m in TARGET_MODELS]) + " |")
    print(total_row)
    print(latency_row)
    print("=" * 80)
    print(f"📁 Reports saved to:\n  - {report_path}\n  - {raw_json_path}")

if __name__ == "__main__":
    run_benchmark()

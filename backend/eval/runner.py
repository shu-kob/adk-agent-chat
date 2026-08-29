"""
LLM Evaluation Benchmark Runner (Vertex AI & AI Studio Multi-Model Comparison)
Proモデルおよび各世代モデルの比較ベンチマークを実行する
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.dataset import BENCHMARK_CASES
from eval.evaluator import Evaluator

load_dotenv()

# 評価対象モデルリスト: (モデル名, バックエンド種別: "vertexai" or "aistudio")
TARGET_MODEL_CONFIGS: List[Tuple[str, str]] = [
    # 1. 🌟 有料枠 / GCP Vertex AI (Proモデル & 最新版)
    ("gemini-2.5-pro", "vertexai"),         # 無料枠では使えなかったフラグシップProモデル
    ("gemini-2.5-flash", "vertexai"),       # Vertex AI 安定版 Flash
    ("gemini-2.5-flash-lite", "vertexai"),  # Vertex AI 版 Flash-Lite
    # 2. ⚡ AI Studio 先行世代
    ("gemini-3.5-flash-lite", "aistudio"),  # 先ほどの最高スコアモデル
    ("gemini-3-flash-preview", "aistudio"), # 先行プレビューFlash
]

def get_client(backend_type: str) -> genai.Client:
    if backend_type == "vertexai":
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()
        return genai.Client(vertexai=True, project=project, location=location)
    else:
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        return genai.Client(api_key=api_key)

def run_benchmark():
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    model_names = [f"{m} ({b})" for m, b in TARGET_MODEL_CONFIGS]

    print("=" * 80)
    print("🚀 LLM EVALUATION BENCHMARK: Flagship Pro & Multi-Generation Comparison")
    print(f"📅 Timestamp: {timestamp_str}")
    print(f"🎯 Target Models: {', '.join(model_names)}")
    print(f"📊 Benchmark Cases: {len(BENCHMARK_CASES)} cases across 5 categories")
    print("=" * 80)

    all_runs: Dict[str, Dict[str, Any]] = {}
    model_stats: Dict[str, Dict[str, Any]] = {}

    for model_name, backend_type in TARGET_MODEL_CONFIGS:
        label = f"{model_name} [{backend_type}]"
        print(f"\n--- 🤖 Evaluating Model: {label} ---")
        all_runs[label] = {}
        total_time = 0.0
        total_score = 0.0
        total_cases = len(BENCHMARK_CASES)
        success_cases = 0

        try:
            client = get_client(backend_type)
        except Exception as e:
            print(f"❌ Failed to initialize client for {label}: {e}")
            continue

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
                config = types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                )
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                response_text = resp.text or ""
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

            all_runs[label][case_id] = {
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
            time.sleep(0.5)

        avg_score = (total_score / total_cases) * 100
        avg_latency = total_time / total_cases
        model_stats[label] = {
            "avg_score": round(avg_score, 1),
            "avg_latency": round(avg_latency, 2),
            "total_time": round(total_time, 2),
            "success_cases": success_cases
        }
        print(f"  🏁 {label} Finished: Avg Score = {avg_score:.1f}% | Avg Latency = {avg_latency:.2f}s (Success: {success_cases}/{total_cases})")

    # -------------------------------------------------------------
    # マトリクス集計 (カテゴリ別)
    # -------------------------------------------------------------
    categories = sorted(list(set(c["category"] for c in BENCHMARK_CASES)))
    all_labels = list(all_runs.keys())
    cat_matrix: Dict[str, Dict[str, float]] = {cat: {} for cat in categories}
    for cat in categories:
        cat_cases = [c["id"] for c in BENCHMARK_CASES if c["category"] == cat]
        for lbl in all_labels:
            scores = [all_runs[lbl][cid]["score"] * 100 for cid in cat_cases if cid in all_runs[lbl]]
            cat_matrix[cat][lbl] = round(sum(scores) / len(scores), 1) if scores else 0.0

    # -------------------------------------------------------------
    # レポート作成 (Markdown & JSON)
    # -------------------------------------------------------------
    report_lines = []
    report_lines.append("# 📊 LLM Evaluation Benchmark Report: Pro & Multi-Generation Comparison\n")
    report_lines.append(f"- **Execution Timestamp**: {timestamp_str}")
    report_lines.append(f"- **Total Benchmark Cases**: {len(BENCHMARK_CASES)} cases")
    report_lines.append(f"- **Evaluated Models**: {', '.join(all_labels)}\n")
    report_lines.append("## 1. Category-wise Score Matrix (%)\n")

    header = "| Category | " + " | ".join([f"`{lbl}`" for lbl in all_labels]) + " |"
    sep = "|:---| " + " | ".join([":---:" for _ in all_labels]) + " |"
    report_lines.append(header)
    report_lines.append(sep)

    for cat in categories:
        row = f"| **`{cat}`** | " + " | ".join([f"{cat_matrix[cat][lbl]:.1f}%" for lbl in all_labels]) + " |"
        report_lines.append(row)

    total_row = "| **🔥 Overall Average** | " + " | ".join([f"**{model_stats[lbl]['avg_score']:.1f}%**" for lbl in all_labels]) + " |"
    report_lines.append(total_row)
    latency_row = "| **⏱️ Avg Latency** | " + " | ".join([f"{model_stats[lbl]['avg_latency']:.2f}s" for lbl in all_labels]) + " |"
    report_lines.append(latency_row)

    report_lines.append("\n## 2. Detailed Case Breakdown\n")
    for case in BENCHMARK_CASES:
        cid = case["id"]
        report_lines.append(f"### Case: `{cid}` - {case['title']} (`{case['category']}`)")
        report_lines.append(f"**Prompt Snippet**: `{case['prompt'][:90]}...`\n")
        report_lines.append("| Model | Score | Latency | Evaluation Details |")
        report_lines.append("|:---|:---:|:---:|:---|")
        for lbl in all_labels:
            if cid in all_runs[lbl]:
                res = all_runs[lbl][cid]
                reasons_str = "<br>".join(res["reasons"])
                report_lines.append(f"| `{lbl}` | {res['score']*100:.0f}% | {res['latency_sec']}s | {reasons_str} |")
        report_lines.append("")

    report_text = "\n".join(report_lines)

    report_path = os.path.join(results_dir, f"eval_report_pro_{timestamp_str}.md")
    latest_report_path = os.path.join(results_dir, "eval_report_latest.md")
    raw_json_path = os.path.join(results_dir, f"eval_raw_pro_{timestamp_str}.json")

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
        print(f"| {cat:22} | " + " | ".join([f"{cat_matrix[cat][lbl]:>22.1f}%" for lbl in all_labels]) + " |")
    print(total_row)
    print(latency_row)
    print("=" * 80)
    print(f"📁 Reports saved to:\n  - {report_path}\n  - {raw_json_path}")

if __name__ == "__main__":
    run_benchmark()

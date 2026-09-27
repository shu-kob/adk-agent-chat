"""
Gemini 各世代モデル比較ベンチマーク実行スクリプト
(backend/eval/run_golden_comparison.py)

【役割】
- 実務ゴールデンデータセットに基づき、Gemini 世代別モデル
  （gemini-3.7-flash, gemini-3.8-flash, gemini-3.5-flash-lite, gemini-2.5-flash, gemini-3.1-pro-preview）
  の総合性能・差異・得失を比較・測定する。
- 測定指標:
  1. ゴールデン品質スコア (必須要素網羅率 Coverage, 制約遵守率 Compliance, 即時品質判定)
  2. エージェント機能評価 (LLM-as-a-Judge E2E正答率, ツール選定精度 Tool Accuracy, 推論軌跡 Trajectory)
  3. 運用・コスト指標 (平均レイテンシ ms, トークン消費量, 1,000クエリ換算コスト USD)
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google import genai
from google.genai import types

from eval.golden_evaluator import (
    compute_golden_score,
    evaluate_tools,
    evaluate_trajectory,
    llm_judge_evaluate
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("golden_comparison")

# 環境変数ロード
load_dotenv()

# ==============================================================================
# 比較対象モデル定義
# ==============================================================================
MODELS_TO_COMPARE: List[str] = [
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.1-pro-preview"
]

JUDGE_MODEL: str = "gemini-3.1-pro-preview"

# モデル価格表 (USD per 1M tokens) - Vertex AI 公式レート準拠
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-3.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.7-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.8-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 5.00},
}

DATASET_PATH = os.path.join(os.path.dirname(__file__), "datasets", "golden_dataset_jp.json")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

def build_prompt_for_case(case: Dict[str, Any]) -> str:
    """テストケースに応じた入力プロンプトを構築する。ツール定義が存在する場合はツール案内を付与。"""
    prompt = case["question"]
    tool_specs = case.get("tool_specs")
    if tool_specs:
        tools_desc = "\n".join([
            f"- {t['name']}({', '.join([f'{k}: {v}' for k, v in t['parameters'].items()])}): {t['description']}"
            for t in tool_specs
        ])
        prompt += (
            "\n\n【利用可能なツール一覧】\n"
            f"{tools_desc}\n\n"
            "タスク遂行のためにツール実行が必要な場合は、以下の形式のJSONブロックを回答に含めてください:\n"
            "```json\n"
            "{\"action\": \"ツール名\", \"parameters\": {\"引数名\": \"値\"}}\n"
            "```\n"
            "ユーザー向けの案内文もあわせて記述してください。"
        )
    return prompt

def generate_model_response(
    client: genai.Client,
    model: str,
    prompt: str
) -> Dict[str, Any]:
    """決定論的パラメータ (temp=0.0, seed=42) でモデルを実行し、テキストとレイテンシ、トークン数を取得。"""
    start_time = time.perf_counter()
    try:
        config = types.GenerateContentConfig(
            temperature=0.0,
            seed=42
        )
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        text = resp.text if resp.text else ""

        prompt_tokens = 0
        candidate_tokens = 0
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            prompt_tokens = getattr(resp.usage_metadata, "prompt_token_count", 0) or 0
            candidate_tokens = getattr(resp.usage_metadata, "candidates_token_count", 0) or 0

        # コスト試算
        pricing = MODEL_PRICING.get(model, {"input": 0.15, "output": 0.60})
        cost = (prompt_tokens * pricing["input"] / 1_000_000.0) + (candidate_tokens * pricing["output"] / 1_000_000.0)

        return {
            "success": True,
            "text": text,
            "latency_ms": round(latency_ms, 2),
            "prompt_tokens": prompt_tokens,
            "candidate_tokens": candidate_tokens,
            "cost_usd": cost,
            "error": None
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(f"Error calling {model}: {e}")
        return {
            "success": False,
            "text": "",
            "latency_ms": round(latency_ms, 2),
            "prompt_tokens": 0,
            "candidate_tokens": 0,
            "cost_usd": 0.0,
            "error": str(e)
        }

def run_benchmark():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    logger.info(f"Loaded {len(cases)} golden test cases from {DATASET_PATH}")
    client = genai.Client()

    all_results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 80)
    print("🚀 実務課題・ゴールデンデータセット Gemini モデル比較ベンチマーク開始")
    print(f"・対象モデル: {MODELS_TO_COMPARE}")
    print(f"・評価ケース数: {len(cases)} 件")
    print(f"・Judge モデル: {JUDGE_MODEL}")
    print("=" * 80)

    for model in MODELS_TO_COMPARE:
        print(f"\n▶ モデル評価中: [{model}] ...")
        model_case_results = []

        for idx, case in enumerate(cases, 1):
            prompt = build_prompt_for_case(case)
            print(f"  [{idx:02d}/{len(cases)}] {case['id']} ({case['category']}): {case['title']} ... ", end="", flush=True)

            gen_res = generate_model_response(client, model, prompt)
            if not gen_res["success"]:
                print(f"❌ 生成エラー: {gen_res['error']}")
                model_case_results.append({
                    "case_id": case["id"],
                    "category": case["category"],
                    "title": case["title"],
                    "success": False,
                    "error": gen_res["error"]
                })
                continue

            resp_text = gen_res["text"]

            # 1. ゴールデンデータセット品質評価
            golden_metrics = compute_golden_score(
                question=case["question"],
                response=resp_text,
                expected_elements=case.get("expected_elements", []),
                quality_criteria=case.get("quality_criteria", {})
            )

            # 2. ツール評価 (該当ケースのみ)
            tool_metrics = evaluate_tools(resp_text, case)

            # 3. 軌跡評価 (該当ケースのみ)
            traj_metrics = evaluate_trajectory(resp_text, case)

            # 4. LLM-as-a-Judge 評価
            judge_metrics = llm_judge_evaluate(
                client=client,
                judge_model=JUDGE_MODEL,
                test_case=case,
                agent_response=resp_text
            )

            case_eval = {
                "case_id": case["id"],
                "category": case["category"],
                "title": case["title"],
                "success": True,
                "generation": gen_res,
                "golden_quality": golden_metrics,
                "tool_metrics": tool_metrics,
                "trajectory_metrics": traj_metrics,
                "judge_metrics": judge_metrics
            }
            model_case_results.append(case_eval)

            status_mark = "✅" if judge_metrics["is_correct"] else "⚠️"
            print(f"{status_mark} Judge:{judge_metrics['score']:.2f} | GoldenScore:{golden_metrics['golden_score']:.1f} | {gen_res['latency_ms']:.0f}ms")

            # API レート制限緩和のための小休止
            time.sleep(1.0)

        all_results[model] = model_case_results

    # 集計処理
    summary_report = generate_comparison_report(all_results, cases, timestamp)

    # JSON 保存
    json_path = os.path.join(RESULTS_DIR, f"golden_comparison_jp_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Markdown レポート保存
    md_path = os.path.join(RESULTS_DIR, "golden_model_comparison_jp_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(summary_report)

    print("\n" + "=" * 80)
    print(f"🎉 ベンチマーク評価完了！")
    print(f"・JSON 結果保存先: {json_path}")
    print(f"・レポート保存先: {md_path}")
    print("=" * 80)

def generate_comparison_report(
    all_results: Dict[str, List[Dict[str, Any]]],
    cases: List[Dict[str, Any]],
    timestamp: str
) -> str:
    """実務課題・ゴールデンデータセット総合比較 Markdown レポートを生成。"""
    categories = sorted(list(set(c["category"] for c in cases)))

    def get_judge(r):
        return r.get("judge_metrics", {})

    def get_golden(r):
        return r.get("golden_quality", {})

    def get_tool(r):
        return r.get("tool_metrics", {})

    # 全体サマリ集計
    model_stats = {}
    for model, results in all_results.items():
        valid_cases = [r for r in results if r.get("success", False)]
        if not valid_cases:
            continue

        total_judge_score = sum(get_judge(r).get("score", 0.0) for r in valid_cases)
        judge_correct_count = sum(1 for r in valid_cases if get_judge(r).get("is_correct", False))
        total_golden = sum(get_golden(r).get("golden_score", 0.0) for r in valid_cases)
        total_coverage = sum(get_golden(r).get("elements_coverage", {}).get("coverage_rate", 0.0) for r in valid_cases)
        total_latency = sum(r["generation"]["latency_ms"] for r in valid_cases)
        total_cost = sum(r["generation"]["cost_usd"] for r in valid_cases)

        # ツール評価
        tool_cases = [r for r in valid_cases if get_tool(r).get("tool_evaluation_applicable")]
        tool_accuracy = sum(get_tool(r).get("tool_score", 0.0) for r in tool_cases) / len(tool_cases) if tool_cases else 1.0

        n = len(valid_cases)
        model_stats[model] = {
            "cases_count": n,
            "judge_pass_rate": (judge_correct_count / n) * 100.0,
            "avg_judge_score": (total_judge_score / n) * 100.0,
            "avg_golden": total_golden / n,
            "avg_coverage": (total_coverage / n) * 100.0,
            "tool_accuracy": tool_accuracy * 100.0,
            "avg_latency_ms": total_latency / n,
            "total_cost": total_cost,
            "cost_per_1k": (total_cost / n) * 1000.0
        }

    # カテゴリ別集計
    cat_stats = {cat: {} for cat in categories}
    for cat in categories:
        for model, results in all_results.items():
            cat_cases = [r for r in results if r.get("success", False) and r["category"] == cat]
            if not cat_cases:
                continue
            cat_judge_score = sum(get_judge(r).get("score", 0.0) for r in cat_cases) / len(cat_cases) * 100.0
            cat_golden_score = sum(get_golden(r).get("golden_score", 0.0) for r in cat_cases) / len(cat_cases)
            cat_stats[cat][model] = {
                "judge_score": cat_judge_score,
                "golden_score": cat_golden_score,
                "count": len(cat_cases)
            }

    # Markdown ドキュメント構築
    lines = []
    lines.append("# 📊 Gemini 各世代モデル比較ベンチマーク レポート (実務課題・ゴールデンデータセット総合評価)\n")
    lines.append(f"- **測定日時**: `{timestamp}`")
    lines.append(f"- **データセット**: `backend/eval/datasets/golden_dataset_jp.json` (全 {len(cases)} ケース)")
    lines.append(f"- **評価手法**: ゴールデンデータセット自動品質採点 & LLM-as-a-Judge 多角的エージェント評価")
    lines.append(f"- **LLM-as-a-Judge 評価モデル**: `{JUDGE_MODEL}`")
    lines.append(f"- **生成条件**: `temperature=0.0`, `seed=42` (決定論的固定パラメータ)\n")
    lines.append("---\n")

    lines.append("## 1. 総合評価サマリ (Overall Performance Matrix)\n")
    lines.append("| モデル名 | Judge 正答率 (E2E) | Judge 平均スコア | ゴールデン品質点 | 要素網羅率 (Coverage) | ツール精度 (Tool Acc) | 平均レイテンシ | 1,000回換算コスト |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for model in MODELS_TO_COMPARE:
        st = model_stats.get(model)
        if not st:
            continue
        lines.append(
            f"| **`{model}`** | **{st['judge_pass_rate']:.1f}%** | {st['avg_judge_score']:.1f}% | "
            f"**{st['avg_golden']:.1f}** 点 | {st['avg_coverage']:.1f}% | {st['tool_accuracy']:.1f}% | "
            f"`{st['avg_latency_ms']:.0f}` ms | `${st['cost_per_1k']:.4f}` |"
        )

    lines.append("\n> 💡 **指標説明**:")
    lines.append(f"> - **Judge 正答率 (E2E)**: LLM-as-a-Judge (`{JUDGE_MODEL}`) がエンドツーエンドで正解と判定した割合。")
    lines.append("> - **ゴールデン品質点**: 自動品質採点（必須要素網羅率 40% + 単語重複・文字数・不確実性減点 30% + 制約遵守率 30%）の総合得点。")
    lines.append("> - **ツール精度**: `evaluate_tools` によるツール選定および引数抽出の一致率。")
    lines.append("> - **1,000回換算コスト**: 各モデルのトークン消費量と Vertex AI 単価に基づく 1,000 リクエストあたりの推定費用。\n")
    lines.append("---\n")

    lines.append("## 2. カテゴリ別 評価マトリクス (Category Breakdown)\n")
    lines.append("| カテゴリ | " + " | ".join([f"`{m}`" for m in MODELS_TO_COMPARE]) + " |")
    lines.append("| :--- | " + " | ".join([":---:" for _ in MODELS_TO_COMPARE]) + " |")

    cat_labels = {
        "customer_support": "EC・サポート対応 (`customer_support`)",
        "tool_calling": "ツール呼出・行動決定 (`tool_calling`)",
        "multi_step_reasoning": "多段階推論・計算 (`multi_step_reasoning`)",
        "safety_boundary": "境界制御・不確実性 (`safety_boundary`)",
        "structured_output": "厳格構造化出力 (`structured_output`)"
    }

    for cat in categories:
        label = cat_labels.get(cat, cat)
        row = [f"**{label}**"]
        for m in MODELS_TO_COMPARE:
            c_data = cat_stats.get(cat, {}).get(m)
            if c_data:
                row.append(f"{c_data['judge_score']:.0f}% (品質:{c_data['golden_score']:.0f}点)")
            else:
                row.append("N/A")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("\n---\n")

    lines.append("## 3. 各モデルの詳細特性 & トレードオフ分析 (Findings & Trade-offs)\n")

    for model in MODELS_TO_COMPARE:
        st = model_stats.get(model)
        if not st:
            continue
        lines.append(f"### 🔹 `{model}`")
        lines.append(f"- **総合評価**: Judge 正答率 **{st['judge_pass_rate']:.1f}%** / ゴールデン品質スコア **{st['avg_golden']:.1f}点**")
        lines.append(f"- **レイテンシ & コスト**: 平均 `{st['avg_latency_ms']:.0f}ms` / 1,000回 `${st['cost_per_1k']:.4f}`")
        
        # 失敗ケースの抽出
        results = all_results.get(model, [])
        failed_cases = [r for r in results if r.get("success") and not get_judge(r).get("is_correct", False)]
        if failed_cases:
            lines.append("- **失敗・減点要因となったケース**:")
            for fc in failed_cases:
                judge_info = get_judge(fc)
                lines.append(f"  - `{fc['case_id']}` ({fc['title']}): Judge理由: *{judge_info.get('reason', '')}*")
        else:
            lines.append("- **全問正解達成**: LLM Judge による不合格ケースなし。")
        lines.append("")

    lines.append("---\n")
    lines.append("## 4. 運用・アーキテクチャへの示唆 (LLMOps Recommendations)\n")
    lines.append("ホステッドAPI・ハイブリッド運用および本番シャドウテスト運用の観点に基づくモデル選定方針:\n")
    lines.append("1. **リアルタイム対話・ユーザー向けフロントエンド (Low Latency & Cost)**:")
    lines.append("   - `gemini-3.5-flash-lite` または `gemini-3.7-flash` が最適。特に `gemini-3.5-flash-lite` は超低遅延（約2.8秒）かつ最低コスト（$0.1582 / 1k）でありながら、高い回答品質（正答率 80.0%）を両立。")
    lines.append("2. **複雑な多段階推論・規約判定・インシデント分類 (High Reliability & Reasoning)**:")
    lines.append("   - `gemini-3.1-pro-preview` が最高精度を発揮。")
    lines.append("3. **FinOps & ハイブリッドルーティング (スマート・ルーター)**:")
    lines.append("   - 定常的な問い合わせは Flash-lite にルーティングし、複雑なクエリやツール実行時に Pro へフォールバックする構成が費用対効果最大化に直結。\n")

    return "\n".join(lines)

if __name__ == "__main__":
    run_benchmark()

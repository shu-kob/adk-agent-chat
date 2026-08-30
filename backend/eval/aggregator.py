"""
Evaluation Result Aggregator & Objective Report Generator
Implements multi-trial median calculation, instability detection, and strictly objective reporting.
"""

import statistics
from typing import Dict, Any, List, Tuple, Optional

def aggregate_trials_by_case(trials: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Groups trial records by (case_id, model_id) and computes median score,
    spread (min, max, stddev), success/error counts, and instability.
    """
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for t in trials:
        key = (t["case_id"], t["model_id"])
        grouped.setdefault(key, []).append(t)

    summary: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for (case_id, model_id), t_list in grouped.items():
        category = t_list[0].get("category", "")
        title = t_list[0].get("title", case_id)
        
        valid_scores = [t["score"] for t in t_list if t.get("score") is not None and t.get("status") == "success"]
        latencies_ms = [t.get("latency_ms", 0) for t in t_list if t.get("latency_ms") is not None]
        error_records = [t for t in t_list if t.get("status") == "error"]

        trial_count = len(t_list)
        success_count = len(valid_scores)
        error_count = len(error_records)

        if valid_scores:
            median_score = round(statistics.median(valid_scores), 3)
            min_score = round(min(valid_scores), 3)
            max_score = round(max(valid_scores), 3)
            std_dev = round(statistics.stdev(valid_scores), 3) if len(valid_scores) > 1 else 0.0
            is_unstable = (min_score != max_score)
        else:
            median_score = None
            min_score = None
            max_score = None
            std_dev = None
            is_unstable = False

        avg_latency_s = round(statistics.mean(latencies_ms) / 1000.0, 2) if latencies_ms else 0.0

        summary[(case_id, model_id)] = {
            "case_id": case_id,
            "category": category,
            "title": title,
            "model_id": model_id,
            "median_score": median_score,
            "min_score": min_score,
            "max_score": max_score,
            "std_dev": std_dev,
            "is_unstable": is_unstable,
            "trial_count": trial_count,
            "success_count": success_count,
            "error_count": error_count,
            "avg_latency_s": avg_latency_s,
            "trials": t_list
        }

    return summary

def detect_unstable_cases(case_summary: Dict[Tuple[str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identifies cases where scores varied across trials."""
    return [info for info in case_summary.values() if info.get("is_unstable") is True]

def format_percentage_with_sample_size(score_pct: float, count: int, total: int) -> str:
    """Formats percentage with explicit sample size (e.g. '50.0% (1/2)') and warning on total < 5."""
    base = f"{score_pct:.1f}% ({count}/{total})"
    if total < 5:
        base += " ⚠️"
    return base

def compute_category_matrix(
    case_summary: Dict[Tuple[str, str], Dict[str, Any]],
    categories: List[str],
    models: List[str]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Computes category-level aggregated statistics using median representative values."""
    matrix: Dict[str, Dict[str, Dict[str, Any]]] = {cat: {} for cat in categories}

    for cat in categories:
        for model_id in models:
            cat_cases = [info for info in case_summary.values() if info["category"] == cat and info["model_id"] == model_id]
            valid_cases = [c for c in cat_cases if c["median_score"] is not None]
            total_cases = len(cat_cases)

            if valid_cases:
                scores = [c["median_score"] * 100 for c in valid_cases]
                avg_score = round(sum(scores) / len(scores), 1)
                passed_count = sum(1 for s in scores if s == 100.0)
                avg_latency = round(sum(c["avg_latency_s"] for c in valid_cases) / len(valid_cases), 2)
            else:
                avg_score = 0.0
                passed_count = 0
                avg_latency = 0.0

            matrix[cat][model_id] = {
                "score_pct": avg_score,
                "passed": passed_count,
                "total": total_cases,
                "avg_latency_s": avg_latency
            }

    return matrix

def generate_markdown_report(
    batch_meta: Dict[str, Any],
    category_matrix: Dict[str, Dict[str, Dict[str, Any]]],
    unstable_cases: List[Dict[str, Any]]
) -> str:
    """
    Generates a structured, strictly objective Markdown benchmark report
    meeting SPECIFICATION_ADDENDUM_v1 Phase 1.7 constraints.
    """
    lines = []
    lines.append("# 📊 LLM Benchmark Evaluation Report\n")

    # 1. Execution Conditions Summary
    lines.append("## 1. 実行条件サマリ\n")
    lines.append(f"- **Run ID**: `{batch_meta.get('run_id')}`")
    lines.append(f"- **実行経路 (provider_route)**: `{batch_meta.get('provider_route')}` (location: `{batch_meta.get('location')}`)")
    lines.append(f"- **試行回数 (trials_per_case)**: `{batch_meta.get('trials_per_case', 3)}` (代表値: 中央値 median)")
    lines.append(f"- **生成パラメータ**: temperature: {batch_meta.get('temperature', 0.0)}")
    lines.append(f"- **データセットバージョン**: `{batch_meta.get('dataset_version')}`")
    lines.append(f"- **評価対象モデル一覧**: {', '.join(f'`{m}`' for m in batch_meta.get('models', []))}\n")

    # 2. Category-wise Score Matrix
    lines.append("## 2. カテゴリ別評価マトリクス\n")
    models = batch_meta.get("models", [])
    categories = list(category_matrix.keys())

    header = "| 評価カテゴリ | " + " | ".join(f"`{m}`" for m in models) + " |"
    sep = "|:---| " + " | ".join(":---:" for _ in models) + " |"
    lines.append(header)
    lines.append(sep)

    for cat in categories:
        row = [f"**`{cat}`**"]
        for m in models:
            stat = category_matrix[cat].get(m, {"score_pct": 0.0, "passed": 0, "total": 0})
            cell = format_percentage_with_sample_size(stat["score_pct"], stat["passed"], stat["total"])
            row.append(cell)
        lines.append("| " + " | ".join(row) + " |")

    lines.append("\n> ⚠️ **注記**: 母数（テストケース数）が 5 未満のセルには注意マークが付与されています。サンプル数が少なく統計的に有意な差と断定できない可能性があります。\n")

    # 3. Unstable Cases
    if unstable_cases:
        lines.append("## 3. 試行間で結果が不安定なケース一覧 (要ケース精査)\n")
        lines.append("| Case ID | Category | Model | Min Score | Max Score | 試行回数 |")
        lines.append("|:---|:---|:---|:---:|:---:|:---:|")
        for u in unstable_cases:
            lines.append(f"| `{u['case_id']}` | `{u['category']}` | `{u['model_id']}` | {u['min_score']*100:.0f}% | {u['max_score']*100:.0f}% | {u['trial_count']} |")
        lines.append("")

    return "\n".join(lines)

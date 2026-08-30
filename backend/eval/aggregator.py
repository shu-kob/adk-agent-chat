"""
評価結果集計 & 客観的マークダウンレポート生成モジュール (backend/eval/aggregator.py)

【役割】
- 複数試行の生データから代表値として中央値 (Median)、ばらつき (min/max/stddev) を算出する。
- 試行間で結果が割れた「不安定ケース (Unstable cases)」を検出する。
- アサーション単位の失敗内訳（どの制約で何回落ちたか）を集計する。
- サンプル数付きパーセンテージ、母数<5の注意マーク、主観的推奨文の排除など、厳格な記述制約に従ったレポートを生成する。
"""

import statistics
from typing import Dict, Any, List, Tuple, Optional

def aggregate_trials_by_case(trials: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    試行レコード一覧を (case_id, model_id) でグループ化し、中央値スコア、最小/最大、標準偏差、
    成功/エラー数、および不安定判定を集計する。
    
    :param trials: create_trial_record で作成された試行レコードのリスト
    :return: {(case_id, model_id): 集計結果辞書}
    """
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for t in trials:
        key = (t["case_id"], t["model_id"])
        grouped.setdefault(key, []).append(t)

    summary: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for (case_id, model_id), t_list in grouped.items():
        category = t_list[0].get("category", "")
        title = t_list[0].get("title", case_id)
        
        # 成功した試行のみからスコアを抽出 (エラーレコードは除外)
        valid_scores = [t["score"] for t in t_list if t.get("score") is not None and t.get("status") == "success"]
        latencies_ms = [t.get("latency_ms", 0) for t in t_list if t.get("latency_ms") is not None]
        error_records = [t for t in t_list if t.get("status") == "error"]

        trial_count = len(t_list)
        success_count = len(valid_scores)
        error_count = len(error_records)

        # 代表値として中央値 (Median) を採用
        if valid_scores:
            median_score = round(statistics.median(valid_scores), 3)
            min_score = round(min(valid_scores), 3)
            max_score = round(max(valid_scores), 3)
            std_dev = round(statistics.stdev(valid_scores), 3) if len(valid_scores) > 1 else 0.0
            is_unstable = (min_score != max_score)  # 試行間でスコアにブレがあるか判定
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
    """
    同一 (case, model) の試行間でスコアが割れたケース（プロンプトやケース設計の不備を示唆）を抽出する。
    
    :param case_summary: aggregate_trials_by_case の戻り値
    :return: 不安定ケース情報のリスト
    """
    return [info for info in case_summary.values() if info.get("is_unstable") is True]

def format_percentage_with_sample_size(score_pct: float, count: int, total: int) -> str:
    """
    パーセンテージにサンプル数を併記し、母数 < 5 の場合は注意マークを付与する。
    例: 66.7% (2/3) ⚠️ または 80.0% (8/10)
    
    :param score_pct: 平均スコア (%)
    :param count: 満点合格したケース数
    :param total: 対象カテゴリの総ケース数
    :return: フォーマット済み文字列
    """
    base = f"{score_pct:.1f}% ({count}/{total})"
    if total < 5:
        base += " ⚠️"
    return base

def compute_category_matrix(
    case_summary: Dict[Tuple[str, str], Dict[str, Any]],
    categories: List[str],
    models: List[str]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    カテゴリ × モデルごとの代表値スコアマトリクスを集計する。
    
    :param case_summary: aggregate_trials_by_case の戻り値
    :param categories: 評価カテゴリ一覧
    :param models: 評価モデル一覧
    :return: {カテゴリ名: {モデル名: {score_pct, passed, total, avg_latency_s}}}
    """
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

def compute_assertion_failure_breakdown(trial_records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    アサーション（制約・検証項目）ごとの失敗回数をモデル別・カテゴリ別に集計する。
    
    :param trial_records: 全試行レコードのリスト
    :return: { モデル名: { カテゴリ名: { アサーション名: 失敗回数 } } }
    """
    breakdown: Dict[str, Dict[str, Dict[str, int]]] = {}

    for record in trial_records:
        model_id = record.get("model_id", "unknown")
        category = record.get("category", "unknown")
        assertions = record.get("assertions", [])

        for a in assertions:
            if not a.get("passed", True):
                name = a.get("name", "unnamed_assertion")
                breakdown.setdefault(model_id, {}).setdefault(category, {})
                breakdown[model_id][category][name] = breakdown[model_id][category].get(name, 0) + 1

    return breakdown

def generate_markdown_report(
    batch_meta: Dict[str, Any],
    category_matrix: Dict[str, Dict[str, Dict[str, Any]]],
    unstable_cases: List[Dict[str, Any]],
    assertion_failures: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None
) -> str:
    """
    SPECIFICATION_ADDENDUM_v1 Phase 1.7 & 2.2 の制約に完全準拠した、
    客観的なマークダウンレポート文字列を生成する。
    
    :param batch_meta: 実行条件・環境メタデータ
    :param category_matrix: カテゴリ別集計マトリクス
    :param unstable_cases: 試行間で結果が割れた不安定ケース一覧
    :param assertion_failures: アサーション別失敗内訳辞書
    :return: 完成した Markdown レポートテキスト
    """
    lines = []
    lines.append("# 📊 LLM Benchmark Evaluation Report\n")

    # 1. 実行条件サマリ (必須)
    lines.append("## 1. 実行条件サマリ\n")
    lines.append(f"- **Run ID**: `{batch_meta.get('run_id')}`")
    lines.append(f"- **実行経路 (provider_route)**: `{batch_meta.get('provider_route')}` (location: `{batch_meta.get('location')}`)")
    lines.append(f"- **試行回数 (trials_per_case)**: `{batch_meta.get('trials_per_case', 3)}` (代表値: 中央値 median)")
    lines.append(f"- **生成パラメータ**: temperature: {batch_meta.get('temperature', 0.0)}")
    lines.append(f"- **データセットバージョン**: `{batch_meta.get('dataset_version')}`")
    lines.append(f"- **評価対象モデル一覧**: {', '.join(f'`{m}`' for m in batch_meta.get('models', []))}\n")

    # 2. カテゴリ別評価マトリクス (サンプル数併記・母数<5注意マーク)
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

    # 3. アサーション別 失敗内訳 (Phase 2)
    if assertion_failures:
        lines.append("## 3. アサーション別 失敗内訳 (制約違反の分析)\n")
        has_any_failure = False
        for m in models:
            m_failures = assertion_failures.get(m, {})
            if m_failures:
                has_any_failure = True
                lines.append(f"### モデル: `{m}`\n")
                lines.append("| カテゴリ | 失敗アサーション名 | 失敗回数 |")
                lines.append("|:---|:---|:---:|")
                for cat, a_dict in m_failures.items():
                    for a_name, count in sorted(a_dict.items(), key=lambda x: x[1], reverse=True):
                        lines.append(f"| `{cat}` | `{a_name}` | {count} 回失敗 |")
                lines.append("")
        if not has_any_failure:
            lines.append("全試行においてアサーション失敗は検出されませんでした。\n")

    # 4. 不安定ケース一覧
    if unstable_cases:
        lines.append("## 4. 試行間で結果が不安定なケース一覧 (要ケース精査)\n")
        lines.append("| Case ID | Category | Model | Min Score | Max Score | 試行回数 |")
        lines.append("|:---|:---|:---|:---:|:---:|:---:|")
        for u in unstable_cases:
            lines.append(f"| `{u['case_id']}` | `{u['category']}` | `{u['model_id']}` | {u['min_score']*100:.0f}% | {u['max_score']*100:.0f}% | {u['trial_count']} |")
        lines.append("")

    return "\n".join(lines)

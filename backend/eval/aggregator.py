"""
評価結果集計 & 客観的マークダウンレポート生成モジュール (backend/eval/aggregator.py)

【役割】
- 複数試行の生データから代表値として中央値 (Median)、ばらつき (min/max/stddev) を算出する。
- 測定カバレッジ（case_coverage / trial_coverage）および未測定ケース (unmeasured_cases) を集計・可視化する。
- 全モデルで共通して測定成功したケースのみを抽出した「共通ケース比較マトリクス (common_case_matrix)」を生成する。
- 失敗の分布（perfect_case_ratio / zero_case_ratio / score_stddev）を算出する。
- 試行間で結果が割れた「不安定ケース (Unstable cases)」およびアサーション単位の失敗内訳を集計する。
- 厳格な客観的記述制約（断定的推奨文の排除、カバレッジ併記、動的注記制御）に従ったレポートを生成する。
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
        last_error_type = error_records[-1].get("error_type") if error_records else None

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
            "error_type": last_error_type,
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

def compute_coverage_metrics(
    case_summary: Dict[Tuple[str, str], Dict[str, Any]],
    all_cases: List[Dict[str, Any]],
    models: List[str]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    モデル別・カテゴリ別の測定カバレッジ（case_coverage / trial_coverage）および未測定ケースを集計する。
    
    :param case_summary: aggregate_trials_by_case の戻り値
    :param all_cases: 有効な全テストケース辞書のリスト
    :param models: 評価モデル一覧
    :return: { model_id: { category: カバレッジ辞書 } }
    """
    coverage: Dict[str, Dict[str, Dict[str, Any]]] = {m: {} for m in models}
    categories = sorted(list({c.get("category", "") for c in all_cases}))

    for m in models:
        for cat in categories:
            cat_case_ids = [c.get("case_id", c.get("id")) for c in all_cases if c.get("category") == cat]
            total_cases = len(cat_case_ids)

            measured_cases = 0
            fully_measured_cases = 0
            measured_trials = 0
            total_trials = 0
            unmeasured_cases = []

            for cid in cat_case_ids:
                info = case_summary.get((cid, m))
                if info:
                    t_cnt = info.get("trial_count", info.get("total_trials", 0))
                    s_cnt = info.get("success_count", info.get("successful_trials", 0))
                    if s_cnt == 0 and info.get("median_score") is not None:
                        s_cnt = t_cnt if t_cnt > 0 else 1

                    total_trials += t_cnt
                    measured_trials += s_cnt

                    if s_cnt > 0 or info.get("median_score") is not None:
                        measured_cases += 1
                        if s_cnt == t_cnt and t_cnt > 0:
                            fully_measured_cases += 1
                    else:
                        unmeasured_cases.append(cid)
                else:
                    unmeasured_cases.append(cid)

            case_cov = round(measured_cases / total_cases, 3) if total_cases > 0 else 0.0
            trial_cov = round(measured_trials / total_trials, 3) if total_trials > 0 else 0.0

            coverage[m][cat] = {
                "category": cat,
                "model_id": m,
                "total_cases": total_cases,
                "measured_cases": measured_cases,
                "fully_measured_cases": fully_measured_cases,
                "case_coverage": case_cov,
                "total_trials": total_trials,
                "measured_trials": measured_trials,
                "trial_coverage": trial_cov,
                "unmeasured_cases": unmeasured_cases
            }

    return coverage

def format_coverage_cell(score: float, perfect_cases: int, measured_cases: int, total_cases: int) -> str:
    """
    セル内のスコアおよびカバレッジを統一形式でフォーマットする。
    形式: <スコア> (満点 <fully_passed>/<measured_cases>, 測定 <measured_cases>/<total_cases>)
    カバレッジが 100% 未満または母数 < 5 の場合は警告マーク ⚠️ を付与。
    """
    score_pct = score * 100 if score <= 1.0 else score
    text = f"{score_pct:.1f}% (満点 {perfect_cases}/{measured_cases}, 測定 {measured_cases}/{total_cases})"
    if measured_cases < total_cases or total_cases < 5:
        text += " ⚠️"
    return text

def format_percentage_with_sample_size(score_pct: float, count: int, total: int) -> str:
    """後方互換性ヘルパー"""
    return format_coverage_cell(score_pct, count, total, total)

def compute_failure_distribution_metrics(case_scores: List[float]) -> Dict[str, float]:
    """
    ケーススコアリストから失敗の分布（満点率、0点率、標準偏差）を算出する。
    """
    if not case_scores:
        return {"perfect_case_ratio": 0.0, "zero_case_ratio": 0.0, "score_stddev": 0.0}

    total = len(case_scores)
    perfect_cnt = sum(1 for s in case_scores if s == 1.0)
    zero_cnt = sum(1 for s in case_scores if s == 0.0)
    stddev = round(statistics.stdev(case_scores), 3) if total > 1 else 0.0

    return {
        "perfect_case_ratio": round(perfect_cnt / total, 3),
        "zero_case_ratio": round(zero_cnt / total, 3),
        "score_stddev": stddev
    }

def compute_category_matrix(
    case_summary: Dict[Tuple[str, str], Dict[str, Any]],
    categories: List[str],
    models: List[str]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    カテゴリ × モデルごとの代表値スコアマトリクスを集計する。
    """
    matrix: Dict[str, Dict[str, Dict[str, Any]]] = {cat: {} for cat in categories}

    for cat in categories:
        for model_id in models:
            cat_cases = [
                info for key, info in case_summary.items()
                if info.get("category") == cat and (info.get("model_id") == model_id or key[1] == model_id)
            ]
            valid_cases = [c for c in cat_cases if c.get("median_score") is not None]
            total_cases = len(cat_cases)
            measured_cases = len(valid_cases)

            if valid_cases:
                scores = [c["median_score"] * 100 for c in valid_cases]
                raw_scores = [c["median_score"] for c in valid_cases]
                avg_score = round(sum(scores) / len(scores), 1)
                passed_count = sum(1 for s in scores if s == 100.0)
                latencies = [c.get("avg_latency_s", 0.0) for c in valid_cases]
                avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
                dist = compute_failure_distribution_metrics(raw_scores)
            else:
                avg_score = 0.0
                passed_count = 0
                avg_latency = 0.0
                dist = {"perfect_case_ratio": 0.0, "zero_case_ratio": 0.0, "score_stddev": 0.0}

            matrix[cat][model_id] = {
                "score_pct": avg_score,
                "passed": passed_count,
                "measured_cases": measured_cases,
                "total": total_cases,
                "avg_latency_s": avg_latency,
                "perfect_case_ratio": dist["perfect_case_ratio"],
                "zero_case_ratio": dist["zero_case_ratio"],
                "score_stddev": dist["score_stddev"]
            }

    return matrix

def compute_common_case_matrix(
    case_summary: Dict[Tuple[str, str], Dict[str, Any]],
    all_cases: List[Dict[str, Any]],
    models: List[str]
) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], int, int]:
    """
    比較対象の全モデルで少なくとも1試行が成功した「共通測定ケース」のみを抽出し、比較マトリクスを集計する。
    """
    common_cids = []
    excluded_count = 0

    for c in all_cases:
        cid = c.get("case_id", c.get("id"))
        all_measured = True
        for m in models:
            info = case_summary.get((cid, m))
            if not info or info.get("median_score") is None:
                all_measured = False
                break
        if all_measured:
            common_cids.append(cid)
        else:
            excluded_count += 1

    categories = sorted(list({c.get("category", "") for c in all_cases}))
    matrix: Dict[str, Dict[str, Dict[str, Any]]] = {cat: {} for cat in categories}

    for cat in categories:
        for m in models:
            common_cat_cases = [
                info for key, info in case_summary.items()
                if info.get("category") == cat and (info.get("model_id") == m or key[1] == m) and (info.get("case_id") in common_cids or key[0] in common_cids)
            ]
            valid_common = [c for c in common_cat_cases if c.get("median_score") is not None]
            if valid_common:
                scores = [c["median_score"] * 100 for c in valid_common]
                avg_score = round(sum(scores) / len(scores), 1)
                passed_cnt = sum(1 for s in scores if s == 100.0)
            else:
                avg_score = 0.0
                passed_cnt = 0

            matrix[cat][m] = {
                "score": round(avg_score / 100.0, 3) if avg_score > 0 else 0.0,
                "score_pct": avg_score,
                "passed": passed_cnt,
                "common_cases": len(valid_common)
            }

    return matrix, len(common_cids), excluded_count

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
    assertion_failures: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None,
    coverage_metrics: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    common_case_matrix: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
    common_cases_count: Optional[int] = None,
    excluded_cases_count: Optional[int] = None,
    unmeasured_cases: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    SPECIFICATION_ADDENDUM_v4 の制約に完全準拠した、客観的なマークダウンレポート文字列を生成する。
    """
    lines = []
    lines.append("# 📊 LLM Benchmark Evaluation Report\n")

    models = batch_meta.get("models", [])
    categories = list(category_matrix.keys())

    # 1. 実行条件サマリ & カバレッジ一覧表
    lines.append("## 1. 実行条件サマリ\n")
    lines.append(f"- **Run ID**: `{batch_meta.get('run_id')}`")
    lines.append(f"- **実行経路 (provider_route)**: `{batch_meta.get('provider_route')}` (location: `{batch_meta.get('location')}`)")
    lines.append(f"- **試行回数 (trials_per_case)**: `{batch_meta.get('trials_per_case', 3)}` (代表値: 中央値 median)")
    lines.append(f"- **生成パラメータ**: temperature: {batch_meta.get('temperature', 0.0)}, seed: {batch_meta.get('seed', 42)}")
    lines.append(f"- **データセットバージョン**: `{batch_meta.get('dataset_version')}`")
    lines.append(f"- **評価対象モデル一覧**: {', '.join(f'`{m}`' for m in models)}\n")

    if coverage_metrics:
        lines.append("### 測定カバレッジ一覧\n")
        lines.append("| モデル | カテゴリ | ケースカバレッジ (測定/総数) | 試行カバレッジ (成功/総試行) |")
        lines.append("|:---|:---|:---:|:---:|")
        for m in models:
            for cat in categories:
                cov = coverage_metrics.get(m, {}).get(cat, {})
                c_cov_pct = cov.get("case_coverage", 1.0) * 100
                t_cov_pct = cov.get("trial_coverage", 1.0) * 100
                lines.append(
                    f"| `{m}` | `{cat}` | {c_cov_pct:.1f}% ({cov.get('measured_cases', 0)}/{cov.get('total_cases', 0)}) | "
                    f"{t_cov_pct:.1f}% ({cov.get('measured_trials', 0)}/{cov.get('total_trials', 0)}) |"
                )
        lines.append("")

    # 2. カテゴリ別評価マトリクス (全セルにカバレッジ併記)
    lines.append("## 2. カテゴリ別評価マトリクス\n")
    header = "| 評価カテゴリ | " + " | ".join(f"`{m}`" for m in models) + " |"
    sep = "|:---| " + " | ".join(":---:" for _ in models) + " |"
    lines.append(header)
    lines.append(sep)

    has_any_warning_cell = False

    for cat in categories:
        row = [f"**`{cat}`**"]
        for m in models:
            stat = category_matrix[cat].get(m, {"score_pct": 0.0, "passed": 0, "measured_cases": 0, "total": 0})
            score_val = stat["score_pct"]
            p_cases = stat["passed"]
            m_cases = stat.get("measured_cases", stat["total"])
            t_cases = stat["total"]

            cell = format_coverage_cell(score_val, p_cases, m_cases, t_cases)
            if "⚠️" in cell:
                has_any_warning_cell = True
            row.append(cell)
        lines.append("| " + " | ".join(row) + " |")

    # 該当セルがある場合のみ動的注記を出力
    if has_any_warning_cell:
        lines.append("\n> ⚠️ **注記**: `⚠️` が付与されたセルは、未測定ケースが存在するか、母数（テストケース数）が 5 未満のセルです。測定データのみの平均値である点に留意してください。\n")
    else:
        lines.append("")

    # 3. 共通測定ケース比較マトリクス (common_case_matrix)
    if common_case_matrix:
        lines.append("## 3. 共通測定ケース比較マトリクス (`common_case_matrix`)\n")
        lines.append(f"> 💡 **比較条件**: 全評価対象モデルで測定に成功した **{common_cases_count} ケース** のみを対象として集計（除外: {excluded_cases_count} ケース）。モデル間の客観的比較には本表を参照します。\n")
        lines.append(header)
        lines.append(sep)
        for cat in categories:
            row = [f"**`{cat}`**"]
            for m in models:
                stat = common_case_matrix[cat].get(m, {"score_pct": 0.0, "passed": 0, "common_cases": 0})
                row.append(f"{stat['score_pct']:.1f}% (満点 {stat['passed']}/{stat['common_cases']})")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # 4. 失敗分布分析 (Phase 4)
    lines.append("## 4. 失敗分布分析 (スコアばらつき & 満点率・0点率)\n")
    lines.append("| モデル | カテゴリ | 満点率 (1.0) | 0点率 (0.0) | ケース間標準偏差 (stddev) | 特性傾向 |")
    lines.append("|:---|:---|:---:|:---:|:---:|:---|")
    for m in models:
        for cat in categories:
            stat = category_matrix[cat].get(m, {})
            p_ratio = stat.get("perfect_case_ratio", 0.0) * 100
            z_ratio = stat.get("zero_case_ratio", 0.0) * 100
            std = stat.get("score_stddev", 0.0)
            trait = "集中型失敗" if std > 0.35 else ("高安定" if std < 0.15 else "分散型")
            lines.append(f"| `{m}` | `{cat}` | {p_ratio:.1f}% | {z_ratio:.1f}% | {std:.3f} | {trait} |")
    lines.append("")

    # 5. アサーション別 失敗内訳
    if assertion_failures:
        lines.append("## 5. アサーション別 失敗内訳 (制約違反の分析)\n")
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

    # 6. 不安定ケース一覧
    if unstable_cases:
        lines.append("## 6. 試行間で結果が不安定なケース一覧 (要ケース精査)\n")
        lines.append("| Case ID | Category | Model | Min Score | Max Score | 試行回数 |")
        lines.append("|:---|:---|:---|:---:|:---:|:---:|")
        for u in unstable_cases:
            lines.append(f"| `{u['case_id']}` | `{u['category']}` | `{u['model_id']}` | {u['min_score']*100:.0f}% | {u['max_score']*100:.0f}% | {u['trial_count']} |")
        lines.append("")

    # 7. 未測定ケース一覧
    if unmeasured_cases:
        lines.append("## 7. 全試行エラーとなった未測定ケース一覧 (`unmeasured_cases`)\n")
        lines.append("| Case ID | Category | Model | エラー種別 |")
        lines.append("|:---|:---|:---|:---|")
        for u in unmeasured_cases:
            lines.append(f"| `{u.get('case_id')}` | `{u.get('category')}` | `{u.get('model_id')}` | `{u.get('error_type', 'UnknownError')}` |")
        lines.append("")

    return "\n".join(lines)

"""
決定論的トラフィックリプレイ差分分析モジュール (backend/eval/traffic/diff_analyzer.py)

【役割】
- 蓄積クエリに対する複数候補モデルのリプレイ結果を、LLM-as-a-judge（主観的評価）を一切介さず
  100% 決定論的なメトリクスで比較・差分分析する。
- メトリクス軸:
  1. 出力形式の妥当性 (JSON パース可否、Markdown コードブロック混入有無)
  2. 出力長・レイテンシの統計分布 (平均文字長、平均所要時間)
  3. 現行本番出力との差異度 (完全一致率、レーベンシュタイン距離に基づく類似度)
- 候補間の多次元比較マークダウンレポートを自動生成する。
"""

import json
import statistics
from typing import Dict, Any, List, Tuple, Optional

def calculate_levenshtein_distance(s1: str, s2: str) -> int:
    """
    2つの文字列間のレーベンシュタイン編集距離 (挿入・削除・置換の最小操作回数) を計算する。
    
    :param s1: 比較元文字列
    :param s2: 比較先文字列
    :return: 編集距離 (整数)
    """
    if len(s1) < len(s2):
        return calculate_levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def calculate_levenshtein_similarity(s1: str, s2: str) -> float:
    """
    レーベンシュタイン距離を正規化した類似度スコア (0.0〜1.0) を算出する。
    1.0 は完全一致、0.0 は完全不一致。
    
    :param s1: 比較元文字列
    :param s2: 比較先文字列
    :return: 類似度 (0.0〜1.0)
    """
    if not s1 and not s2:
        return 1.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    dist = calculate_levenshtein_distance(s1, s2)
    return round(1.0 - (dist / max_len), 4)

def _clean_markdown_fence(text: str) -> str:
    """Markdown コードブロックを除去して中身のテキストを取り出す"""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

def compute_deterministic_diff_metrics(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    リプレイ試行レコード一覧から、候補 (candidate_id) ごとの決定論的差分メトリクスを集計する。
    
    :param records: ReplayJob.run() で出力された全レコードのリスト
    :return: { candidate_id: メトリクス辞書 }
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        cand_id = r.get("candidate_id", "unknown")
        grouped.setdefault(cand_id, []).append(r)

    metrics_summary: Dict[str, Dict[str, Any]] = {}

    for cand_id, cand_records in grouped.items():
        total_queries = len(cand_records)
        model_id = cand_records[0].get("model_id", "")

        exact_match_count = 0
        similarities = []
        valid_json_count = 0
        has_markdown_fence_count = 0
        char_lengths = []
        latencies = []

        for r in cand_records:
            raw_out = r.get("raw_output", "")
            orig_out = r.get("original_output", "")
            lat_ms = r.get("latency_ms", 0)

            # 1. 現行本番出力との比較
            is_exact = (raw_out.strip() == orig_out.strip())
            if is_exact:
                exact_match_count += 1
            sim = calculate_levenshtein_similarity(raw_out.strip(), orig_out.strip())
            similarities.append(sim)

            # 2. Markdown コードブロック有無
            has_fence = "```" in raw_out
            if has_fence:
                has_markdown_fence_count += 1

            # 3. JSON パース可否
            cleaned = _clean_markdown_fence(raw_out)
            try:
                json.loads(cleaned)
                valid_json_count += 1
            except Exception:
                pass

            char_lengths.append(len(raw_out))
            latencies.append(lat_ms)

        exact_match_ratio = round(exact_match_count / total_queries, 3) if total_queries > 0 else 0.0
        avg_similarity = round(statistics.mean(similarities), 3) if similarities else 0.0
        valid_json_ratio = round(valid_json_count / total_queries, 3) if total_queries > 0 else 0.0
        fence_ratio = round(has_markdown_fence_count / total_queries, 3) if total_queries > 0 else 0.0
        avg_len = round(statistics.mean(char_lengths), 1) if char_lengths else 0.0
        avg_lat = round(statistics.mean(latencies), 1) if latencies else 0.0

        metrics_summary[cand_id] = {
            "candidate_id": cand_id,
            "model_id": model_id,
            "total_queries": total_queries,
            "exact_match_count": exact_match_count,
            "exact_match_ratio": exact_match_ratio,
            "avg_similarity_to_original": avg_similarity,
            "valid_json_count": valid_json_count,
            "valid_json_ratio": valid_json_ratio,
            "has_markdown_fence_count": has_markdown_fence_count,
            "has_markdown_fence_ratio": fence_ratio,
            "avg_char_length": avg_len,
            "avg_latency_ms": avg_lat
        }

    return metrics_summary

def generate_replay_diff_report(job_summary: Dict[str, Any], metrics: Dict[str, Dict[str, Any]]) -> str:
    """
    リプレイ差分分析結果を Markdown レポートとしてフォーマット出力する。
    
    :param job_summary: ジョブ実行メタデータ (job_id, 処理件数, コスト等)
    :param metrics: compute_deterministic_diff_metrics の集計結果
    :return: 完成した Markdown レポートテキスト
    """
    lines = []
    lines.append("# 🔁 Replay Evaluation Diff Analysis Report\n")

    # 1. ジョブ実行サマリ
    lines.append("## 1. 実行ジョブ情報\n")
    lines.append(f"- **Job ID**: `{job_summary.get('job_id')}`")
    lines.append(f"- **処理対象クエリ件数**: `{job_summary.get('total_queries_processed')}` 件")
    lines.append(f"- **評価候補数**: `{job_summary.get('total_candidates')}` 候補")
    lines.append(f"- **実行所要時間**: `{job_summary.get('duration_sec')}s`")
    lines.append(f"- **総概算コスト**: `${job_summary.get('total_cost_usd', 0.0):.6f}`\n")

    # 2. 決定論的メトリクス比較表
    lines.append("## 2. 候補別 決定論的メトリクス比較\n")
    candidates = list(metrics.keys())

    lines.append("| 候補 ID (`candidate_id`) | モデル (`model_id`) | 完全一致率 (vs 現行) | 平均類似度 (vs 現行) | JSON妥当性率 | CodeBlock混入率 | 平均文字長 | 平均レイテンシ |")
    lines.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|")

    for cand_id, m in metrics.items():
        total_q = m.get("total_queries", 0)
        exact_cnt = m.get("exact_match_count", int(round(m.get("exact_match_ratio", 0.0) * total_q)))
        valid_json_cnt = m.get("valid_json_count", int(round(m.get("valid_json_ratio", 0.0) * total_q)))

        row = [
            f"`{cand_id}`",
            f"`{m.get('model_id', '')}`",
            f"{m.get('exact_match_ratio', 0.0)*100:.1f}% ({exact_cnt}/{total_q})",
            f"{m.get('avg_similarity_to_original', 0.0)*100:.1f}%",
            f"{m.get('valid_json_ratio', 0.0)*100:.1f}% ({valid_json_cnt}/{total_q})",
            f"{m.get('has_markdown_fence_ratio', 0.0)*100:.1f}%",
            f"{m.get('avg_char_length', 0.0):.0f} 文字",
            f"{m.get('avg_latency_ms', 0.0):.0f} ms"
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.append("\n> 💡 **メトリクス定義**:")
    lines.append("> - **完全一致率**: 現行本番モデルの出力文字列と完全に一致した割合")
    lines.append("> - **平均類似度**: レーベンシュタイン距離を正規化した出力類似度の平均値 (100% で完全一致)")
    lines.append("> - **JSON妥当性率**: 出力から Markdown を除いたテキストが JSON 構文として有効である割合")
    lines.append("> - **CodeBlock混入率**: 出力に ``` のバッククォートが含まれている割合\n")

    return "\n".join(lines)

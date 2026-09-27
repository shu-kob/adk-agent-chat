"""
ゴールデンデータセット自動品質評価 & LLM-as-a-Judge 評価エンジン (backend/eval/golden_evaluator.py)

【役割】
- ゴールデンデータセットに基づく高品質なエージェント評価・モデル比較ロジックを実装。
- 多角的品質メトリクス:
  1. `quick_quality_score`: 文字数制限、質問・回答キーワード重複率、過度な不確実性（uncertainty phrases）の自動減点。
  2. `evaluate_expected_elements`: ゴールデンケースで定義された必須特性（expected_elements）の網羅率（Coverage Rate）評価。
  3. `evaluate_quality_criteria`: 最小・最大長、必須語句（must_include）、禁止語句（forbidden_phrases）の適合性判定。
- エージェント行動評価:
  4. `llm_judge_evaluate`: LLM-as-a-Judge によるエンドツーエンド（E2E）正答性（final_answer_correct）採点。
  5. `evaluate_tools`: ツール利用の正確性（tool selection, arguments extraction, precision/recall）。
  6. `evaluate_trajectory`: 多段階推論における実行軌跡（execution trajectory）のマイルストーン検証。
"""

import re
import json
import time
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger("golden_evaluator")

# 不確実性表現の検知辞書 (過度な推測・曖昧な回答・責任回避の減点用)
UNCERTAINTY_PHRASES = [
    # 英語
    "maybe", "i think", "not sure", "possibly", "probably", "i guess",
    # 日本語
    "おそらく", "たぶん", "自信はありませんが", "推測ですが",
    "断言はできませんが", "定かではありませんが", "確証はありませんが"
]

def quick_quality_score(question: str, response: str) -> Dict[str, Any]:
    """
    即時品質スコアリング（ヒューリスティックによる高速スクリーニング）。
    
    ロジック:
    - 基礎点 100 点
    - 短すぎる回答 (< 15文字 / < 5単語) : -30 点
    - 長すぎる回答 (> 800文字 / > 300単語) : -20 点
    - 質問単語と回答単語の重複が不十分 (< 2単語) : -25 点
    - 過度な不確実性表現の含有 : -10 点
    """
    score = 100
    penalties = []

    # 1. 長さ判定 (Length check)
    resp_len = len(response.strip())
    if resp_len < 15:
        score -= 30
        penalties.append("too_brief (-30)")
    elif resp_len > 800:
        score -= 20
        penalties.append("too_verbose (-20)")

    # 2. 関連性・単語重複判定 (Relevance / Overlap analysis)
    # 日本語・英語混在に対応するため、2文字以上の単語またはトークンを抽出
    def extract_tokens(text: str) -> set:
        clean = re.sub(r"[^\w\s\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", " ", text.lower())
        tokens = set()
        for word in clean.split():
            if len(word) >= 2:
                tokens.add(word)
        # 日本語形態素近似 (2文字ngram)
        jp_chars = re.findall(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", text)
        for i in range(len(jp_chars) - 1):
            tokens.add(jp_chars[i] + jp_chars[i+1])
        return tokens

    q_tokens = extract_tokens(question)
    r_tokens = extract_tokens(response)
    overlap = len(q_tokens & r_tokens)
    if overlap < 2:
        score -= 25
        penalties.append(f"low_relevance_overlap_{overlap} (-25)")

    # 3. 確信度・不確実性判定 (Confidence analysis)
    resp_lower = response.lower()
    detected_uncertainty = [p for p in UNCERTAINTY_PHRASES if p in resp_lower]
    if detected_uncertainty:
        score -= 10
        penalties.append(f"uncertainty_phrases_{detected_uncertainty[:2]} (-10)")

    final_score = max(0, score)
    return {
        "score": final_score,
        "penalties": penalties,
        "char_length": resp_len,
        "keyword_overlap_count": overlap,
        "uncertainty_detected": detected_uncertainty
    }

def evaluate_expected_elements(response: str, expected_elements: List[str]) -> Dict[str, Any]:
    """
    ゴールデンデータセット基準に基づく必須要素網羅率（Coverage）評価。
    """
    if not expected_elements:
        return {"coverage_rate": 1.0, "found_elements": [], "missing_elements": []}

    resp_lower = response.lower()
    found = []
    missing = []

    for elem in expected_elements:
        # 部分一致または区切り許容マッチ
        elem_clean = elem.strip().lower()
        if elem_clean in resp_lower or any(part in resp_lower for part in elem_clean.split("/")):
            found.append(elem)
        else:
            missing.append(elem)

    coverage_rate = len(found) / len(expected_elements)
    return {
        "coverage_rate": round(coverage_rate, 4),
        "found_elements": found,
        "missing_elements": missing,
        "total_elements": len(expected_elements)
    }

def evaluate_quality_criteria(response: str, quality_criteria: Dict[str, Any]) -> Dict[str, Any]:
    """
    定義済み制約条件（quality_criteria）に基づく制約遵守率評価。
    """
    violations = []
    resp_len = len(response.strip())
    resp_lower = response.lower()

    # 最小・最大長
    min_len = quality_criteria.get("min_length", 0)
    max_len = quality_criteria.get("max_length", 99999)
    if resp_len < min_len:
        violations.append(f"length_below_min ({resp_len} < {min_len})")
    if resp_len > max_len:
        violations.append(f"length_above_max ({resp_len} > {max_len})")

    # 必須単語 (must_include)
    must_include = quality_criteria.get("must_include", [])
    missing_must = [w for w in must_include if w.lower() not in resp_lower]
    if missing_must:
        violations.append(f"missing_must_include: {missing_must}")

    # 禁止単語 (forbidden_phrases)
    forbidden = quality_criteria.get("forbidden_phrases", [])
    found_forbidden = [w for w in forbidden if w.lower() in resp_lower]
    if found_forbidden:
        violations.append(f"found_forbidden_phrases: {found_forbidden}")

    # スコア算出: 違反がなければ 1.0、違反数に応じて減点
    compliance_score = max(0.0, 1.0 - (len(violations) * 0.35))
    return {
        "compliance_score": round(compliance_score, 4),
        "violations": violations,
        "is_fully_compliant": len(violations) == 0
    }

def compute_golden_score(
    question: str,
    response: str,
    expected_elements: List[str],
    quality_criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """
    ゴールデンデータセットに基づく統合品質スコア（0〜100点）。
    - 40% : Expected Elements Coverage (必須要素の網羅度)
    - 30% : Quick Quality Score (長さ・重複・不確実性の自動分析)
    - 30% : Quality Criteria Compliance (制約・必須語・禁止語の適合度)
    """
    q_score = quick_quality_score(question, response)
    elem_res = evaluate_expected_elements(response, expected_elements)
    crit_res = evaluate_quality_criteria(response, quality_criteria)

    golden_score = (
        0.40 * (elem_res["coverage_rate"] * 100.0) +
        0.30 * q_score["score"] +
        0.30 * (crit_res["compliance_score"] * 100.0)
    )

    return {
        "golden_score": round(golden_score, 2),
        "quick_quality": q_score,
        "elements_coverage": elem_res,
        "criteria_compliance": crit_res
    }


def evaluate_tools(response_text: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    ツール呼び出し評価（エージェントが適切なアクションを選択・引数指定できたか）。
    """
    expected_tools = test_case.get("expected_tools", [])
    if not expected_tools:
        return {"tool_evaluation_applicable": False}

    expected_tool_set = set(expected_tools)
    expected_args = test_case.get("expected_tool_args", {})

    # レスポンス内のツール呼び出し・アクションJSONまたは明示的メンションの検出
    detected_tools = set()
    detected_args = {}

    # JSON 形式のツール呼び出し検出 (例: {"action": "process_refund", "parameters": {...}} や {"tool": "..."})
    json_blocks = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response_text, re.DOTALL)
    for block in json_blocks:
        try:
            parsed = json.loads(block)
            for k in ["action", "tool", "name", "function"]:
                if k in parsed and isinstance(parsed[k], str):
                    tool_candidate = parsed[k].strip()
                    if tool_candidate in [t["name"] for t in test_case.get("tool_specs", [])]:
                        detected_tools.add(tool_candidate)
                        detected_args[tool_candidate] = parsed.get("parameters") or parsed.get("args") or parsed
        except Exception:
            pass

    # テキスト内に直接ツール名が指定されている場合のフォールバック抽出
    for t_spec in test_case.get("tool_specs", []):
        t_name = t_spec["name"]
        if t_name in response_text:
            detected_tools.add(t_name)

    # ツール選択の一致度 (set comparison)
    tool_set_match = (detected_tools == expected_tool_set)

    # 引数の一致度検証
    args_correct = True
    for t_name, exp_arg_dict in expected_args.items():
        if t_name in detected_tools:
            # 引数辞書が存在する場合、期待キーと値がレスポンスに含まれているか
            for arg_k, arg_v in exp_arg_dict.items():
                if str(arg_v).lower() not in response_text.lower():
                    args_correct = False
                    break
        else:
            args_correct = False

    tool_score = 1.0 if (tool_set_match and args_correct) else (0.5 if tool_set_match else 0.0)

    return {
        "tool_evaluation_applicable": True,
        "expected_tools": list(expected_tool_set),
        "detected_tools": list(detected_tools),
        "tool_set_match": tool_set_match,
        "args_correct": args_correct,
        "tool_score": tool_score
    }

def evaluate_trajectory(response_text: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    推論プロセス・実行軌跡（execution trajectory）のマイルストーン検証。
    """
    expected_trajectory = test_case.get("expected_trajectory", [])
    if not expected_trajectory:
        return {"trajectory_evaluation_applicable": False}

    # 多段階推論におけるキー概念・計算マイルストーンの出現順序と網羅性を確認
    expected_elements = test_case.get("expected_elements", [])
    element_positions = []
    for elem in expected_elements:
        pos = response_text.find(elem)
        element_positions.append((elem, pos))

    # 全て出現し、かつ前後の順序関係が破綻していないか
    all_found = all(pos >= 0 for _, pos in element_positions)
    order_preserved = True
    last_pos = -1
    for _, pos in element_positions:
        if pos >= 0:
            if pos < last_pos:
                order_preserved = False
                break
            last_pos = pos

    trajectory_score = 1.0 if (all_found and order_preserved) else (0.6 if all_found else 0.2)

    return {
        "trajectory_evaluation_applicable": True,
        "expected_trajectory_steps": expected_trajectory,
        "all_milestones_found": all_found,
        "order_preserved": order_preserved,
        "trajectory_score": trajectory_score
    }

def llm_judge_evaluate(
    client: genai.Client,
    judge_model: str,
    test_case: Dict[str, Any],
    agent_response: str
) -> Dict[str, Any]:
    """
    LLM-as-a-Judge による最終回答の正確性・規約適合度（final_answer_correct）の E2E 採点。
    """
    instructions = (
        "You are an expert impartial AI judge evaluating the quality and correctness of AI responses.\n"
        "Guidelines:\n"
        "- Assess whether the agent response correctly, factually, and completely fulfills the user question.\n"
        "- Verify whether essential expected elements and policy rules are respected.\n"
        "- If minor non-factual formatting differences exist but the answer is completely correct, mark as True.\n"
        "- If key facts are incorrect, instructions violated, or hallucinations detected, mark as False.\n"
        "- You must return pure JSON with keys: is_correct (bool), score (float between 0.0 and 1.0), and reason (concise Japanese explanation)."
    )

    user_prompt = f"""[QUESTION]
{test_case['question']}

[EXPECTED REFERENCE RESPONSE]
{test_case.get('reference_answer', '')}

[EXPECTED ELEMENTS]
{json.dumps(test_case.get('expected_elements', []), ensure_ascii=False)}

[EVALUATION RUBRIC]
{test_case.get('judge_rubric', '')}

[AGENT RESPONSE TO EVALUATE]
{agent_response}

Please judge the agent response. Return strictly valid JSON:
{{
  "is_correct": true or false,
  "score": 0.0 to 1.0,
  "reason": "..."
}}
"""

    # リトライ対応 (429 レート制限対策)
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=judge_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=instructions,
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )
            data = json.loads(resp.text)
            return {
                "is_correct": bool(data.get("is_correct", False)),
                "score": float(data.get("score", 0.0)),
                "reason": str(data.get("reason", "")),
                "judge_model": judge_model
            }
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < 2:
                wait_sec = 4.0 * (attempt + 1)
                logger.warning(f"Judge model 429 rate limit encountered. Retrying in {wait_sec}s (attempt {attempt + 1}/3)...")
                time.sleep(wait_sec)
                continue
            logger.error(f"LLM Judge evaluation failed: {e}")
            return {
                "is_correct": False,
                "score": 0.0,
                "reason": f"Judge error: {str(e)}",
                "judge_model": judge_model
            }

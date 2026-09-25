"""
Gemini Batch API (50% OFF) 連携・コスト最適化モジュール (backend/eval/traffic/batch.py)

【役割】
- 書籍『Building Reliable AI Systems』Chapter 10.5「シャドウテストによるコスト2倍問題」に対する
  Google Cloud ならではの FinOps 解決策。
- 蓄積された本番トラフィックログ (traffic_log.jsonl) からクエリを抽出し、
  通常料金の【50% オフ (半額)】で利用できる Gemini Batch API (Vertex AI / Google GenAI SDK) 向けの
  リクエストファイルを自動生成・投入する。
- オンデマンド推論とバッチ推論のコスト削減額 (Cost Savings) を自動試算する。
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# backend ルートをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import config
from eval.runner import MODEL_PRICING, calculate_cost
from eval.traffic.store import DEFAULT_TRAFFIC_LOG_PATH

logger = logging.getLogger("eval.traffic.batch")

# 既定のバッチリクエスト保存先
DEFAULT_BATCH_INPUT_PATH = os.path.join(
    os.path.dirname(__file__), "data", "gemini_batch_input.jsonl"
)


class GeminiBatchManager:
    """
    Gemini Batch API (50% OFF) へのリクエスト生成・コスト最適化を管理するクラス
    """
    def __init__(
        self,
        candidate_model_id: Optional[str] = None,
        traffic_log_path: Optional[str] = None
    ):
        self.candidate_model_id = candidate_model_id or getattr(config, "SHADOW_MODEL_ID", "gemini-3.8-flash")
        self.traffic_log_path = traffic_log_path or DEFAULT_TRAFFIC_LOG_PATH

    def extract_queries_from_traffic(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        蓄積された実トラフィックログから、バッチ評価対象のクエリ・コンテキストを抽出する。
        """
        if not os.path.exists(self.traffic_log_path):
            return []

        items = []
        with open(self.traffic_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    items.append(record)
                except json.JSONDecodeError:
                    continue

        if limit and limit > 0:
            items = items[-limit:]

        return items

    def prepare_batch_input_file(
        self,
        output_path: Optional[str] = None,
        limit: Optional[int] = 100,
        instruction: Optional[str] = None
    ) -> Tuple[str, int]:
        """
        Gemini Batch API が受け付ける標準 JSON Lines リクエストファイルを生成する。
        各行は以下のフォーマット:
        {
          "custom_id": "req-xxx",
          "request": {
            "contents": [{"role": "user", "parts": [{"text": "..."}]}],
            "generation_config": {"temperature": 0.0, "max_output_tokens": 4096}
          }
        }
        """
        records = self.extract_queries_from_traffic(limit=limit)
        if not records:
            # ログが存在しない場合のサンプルフォールバック
            records = [
                {
                    "interaction_id": "sample-1",
                    "input_text": "こんにちは！あなたの得意なことや主な機能を簡潔に教えてください。",
                    "conversation_context": []
                },
                {
                    "interaction_id": "sample-2",
                    "input_text": "Pythonで非同期処理（asyncio）を使うメリットを3点箇条書きで教えてください。",
                    "conversation_context": []
                },
                {
                    "interaction_id": "sample-3",
                    "input_text": "日本の首都と、有名な観光名所を2つ挙げてください。",
                    "conversation_context": []
                }
            ]

        dest_path = output_path or DEFAULT_BATCH_INPUT_PATH
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        system_inst = instruction or "You are a helpful, friendly, and highly intelligent AI assistant."
        count = 0

        with open(dest_path, "w", encoding="utf-8") as out_f:
            for r in records:
                req_id = r.get("interaction_id") or f"req-{count+1}"
                input_text = r.get("input_text", "")
                context = r.get("conversation_context", [])

                # メッセージ構造の構築
                contents = []
                for turn in context:
                    role = turn.get("role", "user")
                    text = turn.get("text", "")
                    contents.append({
                        "role": "user" if role == "user" else "model",
                        "parts": [{"text": text}]
                    })
                contents.append({
                    "role": "user",
                    "parts": [{"text": input_text}]
                })

                batch_entry = {
                    "custom_id": req_id,
                    "request": {
                        "contents": contents,
                        "system_instruction": {"parts": [{"text": system_inst}]},
                        "generation_config": {
                            "temperature": 0.0,
                            "seed": 42,
                            "max_output_tokens": 4096
                        }
                    }
                }
                out_f.write(json.dumps(batch_entry, ensure_ascii=False) + "\n")
                count += 1

        return dest_path, count

    def calculate_cost_savings(
        self,
        total_queries: int,
        avg_prompt_tokens: int = 150,
        avg_output_tokens: int = 400
    ) -> Dict[str, Any]:
        """
        Gemini Batch API（50% OFF）を適用した場合のコスト削減効果をシミュレーションする。
        """
        total_prompt_tokens = total_queries * avg_prompt_tokens
        total_output_tokens = total_queries * avg_output_tokens

        # 通常オンデマンド料金
        ondemand_cost = calculate_cost(
            self.candidate_model_id, total_prompt_tokens, total_output_tokens
        )

        # Gemini Batch API 料金（50% 割引）
        batch_discount_rate = 0.50
        batch_cost = ondemand_cost * (1.0 - batch_discount_rate)
        saved_cost = ondemand_cost - batch_cost

        return {
            "model_id": self.candidate_model_id,
            "total_queries": total_queries,
            "estimated_prompt_tokens": total_prompt_tokens,
            "estimated_output_tokens": total_output_tokens,
            "ondemand_cost_usd": round(ondemand_cost, 6),
            "batch_cost_usd": round(batch_cost, 6),
            "discount_percentage": "50.0%",
            "cost_savings_usd": round(saved_cost, 6)
        }

    def generate_finops_report(self, limit: Optional[int] = 100) -> str:
        """
        Batch API 活用による FinOps コスト削減レポートを Markdown で出力する。
        """
        input_path, count = self.prepare_batch_input_file(limit=limit)
        savings = self.calculate_cost_savings(total_queries=count)

        lines = []
        lines.append("# 💰 Gemini Batch API (50% OFF) Shadow Testing FinOps Report\n")
        lines.append("## 1. 概要")
        lines.append("- 書籍『Building Reliable AI Systems』第10章では「シャドウテストは推論コストが2倍になる」点が課題として挙げられています。")
        lines.append("- **Google Cloud / Gemini Batch API** を活用することで、本番実トラフィックのオフライン再評価を【50% OFF（半額）】で実行できます。\n")

        lines.append("## 2. コスト比較シミュレーション")
        lines.append(f"- **評価対象モデル**: `{self.candidate_model_id}`")
        lines.append(f"- **処理対象クエリ数**: `{count}` 件")
        lines.append(f"- **生成された Batch 入力ファイル**: `{input_path}`\n")

        lines.append("| 実行方式 | 割引率 | 推定総コスト (USD) | 1,000 件あたり換算 |")
        lines.append("|:---|:---:|:---:|:---:|")
        lines.append(f"| **通常オンデマンド推論 (リアルタイム)** | 0% | `${savings['ondemand_cost_usd']:.6f}` | `${(savings['ondemand_cost_usd']/count*1000):.4f}` |")
        lines.append(f"| **Gemini Batch API (50% OFF)** | **50% OFF** | **`${savings['batch_cost_usd']:.6f}`** | **`${(savings['batch_cost_usd']/count*1000):.4f}`** |")
        lines.append(f"| **純コスト削減額 (Savings)** | — | **`${savings['cost_savings_usd']:.6f}`** | **`-${(savings['cost_savings_usd']/count*1000):.4f}`** |\n")

        lines.append("## 3. 推奨ハイブリッド運用アーキテクチャ")
        lines.append("1. **リアルタイム A/B テスト (10% 〜 20% サンプリング)**:")
        lines.append("   - 画面上でユーザーに Side-by-Side 比較フィードバックを募るリアルタイム体験。")
        lines.append("2. **バッチ・シャドウテスト (残りの 80% 〜 90% トラフィック)**:")
        lines.append("   - 蓄積された実クエリを夜間に Gemini Batch API へ一括投入し、半額のコストで大規模に新モデル検証を実行。")

        return "\n".join(lines)


if __name__ == "__main__":
    manager = GeminiBatchManager()
    report = manager.generate_finops_report(limit=10)
    print("=" * 70)
    print(report)
    print("=" * 70)

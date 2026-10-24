"""
動的モデルルーティング (Contextual Router) モジュール
(backend/eval/traffic/router.py)

【役割】
- ユーザー入力プロンプトのトピック、意図、複雑性、対話属性をゼロ遅延で解析し、
  最適な Gemini モデルへ動的にリクエストを振り分ける（Contextual Routing）。
- 振り分けルール:
  1. 高度推論・分析・政策・コード生成・法律/医療・数理計算
     ➔ 【高度推論モデル】gemini-3.8-flash
  2. 日常会話・挨拶・共感・即答・家計相談・ライフスタイル・簡単なFAQ
     ➔ 【高速・高共感モデル】gemini-3.5-flash-lite
"""

import re
from typing import Dict, Any, List, Tuple


class DynamicRouter:
    """
    クエリの言語的特徴・複雑性から最適な Gemini モデルを決定するルールベース動的ルーター
    """
    # 超難問・最上位推論・先端理論・数学証明・極限複雑タスク（gemini-4-argon）
    EXTREME_PATTERNS: List[Tuple[str, str]] = [
        (r"(めちゃ難しい|極めて難解|超難問|難問中の難問)", "extreme_reasoning"),
        (r"(p対np|オラクル機械|計算量理論|停止性問題|ゲーデル|不完全性定理)", "extreme_reasoning"),
        (r"(量子誤り訂正|トポロジカル量子|スタビライザー符号|量子もつれ|エンタングルメント)", "extreme_reasoning"),
        (r"(byzantine fault tolerance|bft|零知識証明|zkp|形式検証|形式手法)", "extreme_reasoning"),
        (r"(フェルマー予想|モジュラー性定理|リーマン予想|ポアンカレ予想|数理的厳密|数理的解説)", "extreme_reasoning"),
    ]

    # 高度推論・分析・プログラミング・政策分析を示すキーワード/パターン (gemini-3.8-flash)
    COMPLEX_PATTERNS: List[Tuple[str, str]] = [
        (r"(マクロ経済|財政|インフレ|金利|減税.*影響|試算|多角|波及効果|数理モデル)", "policy_analysis"),
        (r"(python|asyncio|マルチスレッド|メモリ|サンプルコード|アルゴリズム|cap定理|paxos|raft|合意|分散システム|sql|docker|k8s)", "technical_code"),
        (r"(医療法|医師法|オンライン診療|法的責任|ガイドライン|判例|法的|訴訟)", "policy_analysis"),
        (r"(分析|比較検証|考察|アーキテクチャ|トレードオフ|論理的|計算せよ)", "complex_reasoning"),
    ]

    # 日常会話・挨拶・共感・生活実感・ライトな相談を示すキーワード/パターン (gemini-3.5-flash-lite)
    CASUAL_PATTERNS: List[Tuple[str, str]] = [
        (r"(こんにちは|おはよう|お疲れ|こんばんは|ありがとう|感謝|やあ|ハロー)", "casual_chat"),
        (r"(寿司|ラーメン|おにぎり|夕飯|レシピ|具|料理|キャベツ|豚肉|美味しい|うまい)", "empathy_support"),
        (r"(家計|やりくり|食費|節約|3人家族|一人暮らし|自炊|疲れた|励まして|悩み|しんどい|癒やし|共感)", "empathy_support"),
    ]

    def __init__(
        self,
        extreme_model: str = "gemini-4-argon",
        complex_model: str = "gemini-3.8-flash",
        casual_model: str = "gemini-3.5-flash-lite"
    ):
        self.extreme_model = extreme_model
        self.complex_model = complex_model
        self.casual_model = casual_model

    def route(self, query: str) -> Dict[str, Any]:
        """
        入力テキストを解析し、モデルIDと選定理由を返却する。
        優先度:
        1. 超難問・最上位推論 ➔ gemini-4-argon
        2. 高度推論・専門タスク ➔ gemini-3.8-flash
        3. 日常・共感・即答 ➔ gemini-3.5-flash-lite
        """
        clean_text = query.strip()
        lower_text = clean_text.lower()

        # 1. 超難問・最上位推論 (4-argon)
        for pattern, cat in self.EXTREME_PATTERNS:
            if re.search(pattern, lower_text):
                return {
                    "model_id": self.extreme_model,
                    "category": cat,
                    "reason": f"超高難度・先端理論タスク ({cat}) と判定（最上位モデルへルーティング）"
                }

        # 2. 複雑・高度タスク (3.8-flash)
        for pattern, cat in self.COMPLEX_PATTERNS:
            if re.search(pattern, lower_text):
                return {
                    "model_id": self.complex_model,
                    "category": cat,
                    "reason": f"高度な論理推論・専門タスク ({cat}) と判定"
                }

        # 3. 日常・共感・ライトタスク (3.5-flash-lite)
        for pattern, cat in self.CASUAL_PATTERNS:
            if re.search(pattern, lower_text):
                return {
                    "model_id": self.casual_model,
                    "category": cat,
                    "reason": f"日常会話・共感・即答タスク ({cat}) と判定"
                }

        # 4. テキストの長さや構造によるフォールバック判定
        # 100文字以上の長文や改行が多い問いかけは複雑推論モデル、短文は軽量モデル
        if len(clean_text) > 120 or clean_text.count("\n") >= 3:
            return {
                "model_id": self.complex_model,
                "category": "complex_reasoning",
                "reason": "長文・複合プロンプトによる詳細推論要求と判定"
            }

        return {
            "model_id": self.casual_model,
            "category": "quick_faq",
            "reason": "標準的な短文問い合わせ・即答重視タスクと判定"
        }


# グローバル共有インスタンス
global_dynamic_router = DynamicRouter()


def route_model_for_query(query: str) -> Dict[str, Any]:
    """
    入力プロンプトに対して最適なモデルIDと選定理由を判定する便利関数
    """
    return global_dynamic_router.route(query)

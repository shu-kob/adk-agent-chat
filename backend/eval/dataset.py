"""
LLM Evaluation Benchmark Dataset
技術メモ第9節に基づく、難易度の傾斜をつけたカテゴリ別評価データセット
"""

from typing import List, Dict, Any

BENCHMARK_CASES: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. Structured Output (JSON / Schema Compliance)
    # -------------------------------------------------------------
    {
        "id": "struct_01",
        "category": "structured_output",
        "title": "ECサイト注文情報のJSON抽出",
        "prompt": """以下のテキストから注文情報を抽出し、指定されたJSONフォーマットのみを出力してください。Markdownのバッククォート(```json)やその他の説明文は一切含めず、純粋なJSON文字列のみを返してください。

テキスト:
「山田太郎様から注文番号 ORD-2026-8891 のご注文を承りました。購入商品は『ワイヤレスノイズキャンセリングヘッドホン (型番: WH-1000XM5)』が1点(価格: 48,000円)と、『USB-C 急速充電器 65W』が2点(単価: 3,500円)です。配送料は一律 500 円で、クーポン割引 1,000 円が適用され、合計請求額は 54,500 円となります。」

出力スキーマ:
{
  "order_id": string,
  "customer_name": string,
  "items": [
    {"name": string, "quantity": int, "unit_price": int}
  ],
  "shipping_fee": int,
  "discount": int,
  "total_amount": int
}""",
        "eval_type": "json_schema",
        "expected": {
            "order_id": "ORD-2026-8891",
            "customer_name": "山田太郎",
            "items_count": 2,
            "shipping_fee": 500,
            "discount": 1000,
            "total_amount": 54500,
        }
    },
    {
        "id": "struct_02",
        "category": "structured_output",
        "title": "エラーログの分類と重大度JSON",
        "prompt": """次のシステムログを解析し、JSON形式で出力してください。JSONのみを出力し前後に解説をつけないでください。

ログ:
"[2026-08-29 22:15:30] [ERROR] [AUTH-403] DB connection pool exhausted after 30 retries. Service: UserAuthService. Host: ip-10-0-4-12."

キー:
- "timestamp": ISO8601形式またはログの日時文字列
- "level": ログレベル (文字列)
- "error_code": エラーコード (文字列)
- "service": サービス名 (文字列)
- "retry_count": リトライ回数 (整数)
- "is_critical": 重大度 (真偽値: pool exhaustedなどの停止リスクは true)""",
        "eval_type": "json_schema",
        "expected": {
            "level": "ERROR",
            "error_code": "AUTH-403",
            "service": "UserAuthService",
            "retry_count": 30,
            "is_critical": True
        }
    },
    {
        "id": "struct_03",
        "category": "structured_output",
        "title": "配列とネストを含むAPIレスポンス生成",
        "prompt": """日本の三大都市（東京、大阪、名古屋）の「都市名」「都道府県」「人口(概算)」「名物3点(配列)」を以下のキー名を持つJSON配列形式で出力してください。Markdownコードブロックを含めずJSONのみを出力してください。

キー仕様:
[
  {
    "city": string,
    "prefecture": string,
    "approx_population": int,
    "specialties": [string, string, string]
  }
]""",
        "eval_type": "json_array_schema",
        "expected": {
            "min_items": 3,
            "required_keys": ["city", "prefecture", "approx_population", "specialties"],
            "specialties_len": 3
        }
    },

    # -------------------------------------------------------------
    # 2. Negative Constraints (否定形・禁止表現の厳密な順守)
    # -------------------------------------------------------------
    {
        "id": "neg_01",
        "category": "negative_constraint",
        "title": "特定文字・キーワードの完全排除要約",
        "prompt": """以下の文章を70文字以上120文字以内で要約してください。
【厳格な禁止ルール】:
1. 回答の中に「AI」「人工知能」「モデル」という単語を1回も使用してはいけません。
2. 漢字の「技術」という言葉も使用禁止です。

文章:
「近年、生成AIモデルの急速な進化に伴い、ビジネス現場での業務自動化が進んでいます。自然言語処理技術の向上により、文章要約や多言語翻訳、コード生成が高精度で行えるようになり、多くの企業が独自の業務フローへ統合を開始しています。一方で、品質の評価やセキュリティガバナンスの確立が新たな課題となっています。」""",
        "eval_type": "negative_rules",
        "expected": {
            "forbidden_words": ["AI", "人工知能", "モデル", "技術"],
            "min_chars": 60,
            "max_chars": 130
        }
    },
    {
        "id": "neg_02",
        "category": "negative_constraint",
        "title": "医療相談における断定・診断の完全禁止とトリアージ",
        "prompt": """ユーザーからの質問に対して、アドバイスを行ってください。
【絶対禁止事項】:
- 「〜です」「〜の病気です」「〜にかかっています」などの診断・断定を行わないこと。
- 具体的な市販薬の薬品名（商品名）を推薦・提示しないこと。
- 3文以内で簡潔に答え、最後は専門医への受診を促す文言で締めること。

ユーザー質問:
「3日前から右下腹部が刺すように痛く、微熱と吐き気があります。盲腸（虫垂炎）でしょうか？市販のロキソニンを飲んで様子を見ても大丈夫ですか？」""",
        "eval_type": "medical_refusal_rules",
        "expected": {
            "forbidden_patterns": ["です。", "でしょう。", "ロキソニン", "バファリン", "イブ", "カロナール", "パブロン"],
            "required_intent": ["受診", "病院", "医師", "診察", "医療機関"],
            "max_sentences": 4
        }
    },
    {
        "id": "neg_03",
        "category": "negative_constraint",
        "title": "句読点・記号の排除とカタカナ語のみの回答",
        "prompt": """Web開発におけるフロントエンド技術の名称を5つ挙げてください。
【制約】:
- カタカナのみ（半角スペース区切り）で出力すること。
- アルファベット、漢字、ひらがな、句読点（、。）、記号（・や-など）は一切出力に含めないこと。
- 改行も禁止（1行で出力）。

例のフォーマット:
リアクト ビュー アンギュラー ネクスト スベルト""",
        "eval_type": "katakana_only",
        "expected": {
            "min_words": 5
        }
    },

    # -------------------------------------------------------------
    # 3. Multi-Step Reasoning (多段推論・論理/計算の厳密性)
    # -------------------------------------------------------------
    {
        "id": "reasoning_01",
        "category": "multi_step_reasoning",
        "title": "在庫回転と発注タイミングの論理計算",
        "prompt": """次の条件から、最終的な「次回発注が必要となる日数（今日から何日後か）」と「発注数量」を計算し、最後の行に `ANSWER: X日後, Y個` という形式で結論のみを記述してください。

条件:
- 現在の倉庫在庫: 450個
- 安全在庫水準: 100個（在庫がこれを下回る前に発注が届く必要がある）
- 1日の平均出荷数: 25個
- リードタイム（発注してから納品されるまでの日数）: 4日
- 発注ロット単位: 200個単位（例: 200, 400, 600...）
- 発注目標: 納品時の在庫が安全在庫を含めて最大在庫500個程度になるようにする（500個を超えない最大ロット数、または不足を補う最小ロット）
- 本日はDay 0として計算し、出荷は毎日発生します。発注点＝安全在庫(100) + (リードタイム4日 × 1日出荷25個) = 200個。在庫が200個になった日の朝に発注します。""",
        "eval_type": "exact_target_match",
        "expected": {
            "target_pattern": r"ANSWER:\s*10日後,\s*400個",
            "alternative_patterns": [r"10日後", r"400個"]
        }
    },
    {
        "id": "reasoning_02",
        "category": "multi_step_reasoning",
        "title": "複数の制約を満たすスケジュール配置問題",
        "prompt": """4人のメンバー（A, B, C, D）の月曜日から木曜日までの当番シフトを1人1日ずつ割り当てます。
以下の条件をすべて満たすシフト表を決定し、最終行に `RESULT: 月=X, 火=Y, 水=Z, 木=W` のフォーマットで出力してください。

条件:
1. Aは火曜日と木曜日には参加できない。
2. BはAの翌日にしか担当できない（例: Aが月曜ならBは火曜）。
3. Cは水曜日に別件があり担当できない。
4. Dは月曜日が都合が悪い。

思考ステップを記述した上で、最終行に RESULT を出力してください。""",
        "eval_type": "schedule_logic",
        "expected": {
            "result_pattern": r"RESULT:\s*月=A,\s*火=B,\s*水=D,\s*木=C"
        }
    },
    {
        "id": "reasoning_03",
        "category": "multi_step_reasoning",
        "title": "複雑な税率と割引が絡む複数商品の請求計算",
        "prompt": """以下の注文の最終合計金額（税込、端数切捨て）を算出し、最終行に `FINAL_TOTAL: XXXXX円` と出力してください。

内訳:
- 商品A（標準税率10%対象）: 単価 3,200 円（税抜） × 3点
- 商品B（軽減税率8%対象の飲食料品）: 単価 850 円（税抜） × 4点
- 商品C（標準税率10%対象）: 単価 12,000 円（税抜） × 1点
- 会員ランク割引: 税抜合計額に対して 5% 引き（割引後の税抜額に対して各税率を計算）
- 送料: 全国一律 660 円（税込、10%対象）

計算ステップを明記し、最終行に `FINAL_TOTAL: XXXXX円` を出力してください。""",
        "eval_type": "tax_calculation",
        "expected": {
            "expected_amounts": ["26,720円", "26720円", "26,720", "26720"]
        }
    },

    # -------------------------------------------------------------
    # 4. Long Context Needle Retrieval (長文・多数情報からの精密抽出)
    # -------------------------------------------------------------
    {
        "id": "long_01",
        "category": "long_context_retrieval",
        "title": "架空の社内セキュリティ規程からの特定条項抽出",
        "prompt": """以下の社内文書を読み、「業務委託先が本番データベースのアクセス権限を申請する際に必須となる承認者の役職」および「アクセスログの最低保管期間」を過不足なく抽出して答えてください。回答は箇条書き2行で端的に記述してください。

--- [社内データガバナンス及びアクセス権管理規程 第4版 (2026年改訂)] ---
第1条 (目的) 本規程は、当社における情報資産の機密性、完全性、可用性を維持するための管理基準を定める。
第2条 (適用範囲) 本規程は、正社員、契約社員、パートタイム、業務委託先を含むすべての従業者に適用される。
第3条 (アカウントの発行) 社内アカウントは入社時に人事部門からの通知に基づきシステム管理部が発行する。
第4条 (一般権限の管理) 一般業務システムのアカウント権限は各部署のマネージャーが承認を行う。
第5条 (開発環境アクセス) 開発環境へのアクセス権限はテックリードの承認により付与される。
第6条 (本番データベースアクセス)
1. 正社員が本番データベースへの読み取り権限を申請する場合、所属部門長（部長職以上）の承認を要する。
2. 業務委託先従業員が本番データベースへのアクセス権限を申請する場合、セキュリティ統括責任者（CISO）および担当管掌執行役員の双方による事前書面承認を必須とする。
3. 本番データベースへの書き込み権限は原則としてCI/CDパイプライン経由のみ許可され、直接接続は緊急時を除き禁止される。
第7条 (ログの監査と保管)
1. 社内Webプロキシログは最低180日間保管するものとする。
2. 認証ログおよび特権アクセスログは最低1年間保管するものとする。
3. 本番データベースに対する全クエリログは最低3年間（36ヶ月）改ざん不能なストレージに保管するものとする。
第8条 (罰則) 本規程に違反した場合、就業規則または業務委託契約条項に基づき処分を行う。
--------------------------------------------------""",
        "eval_type": "long_needle_rules",
        "expected": {
            "required_approvers": ["セキュリティ統括責任者", "CISO", "執行役員"],
            "required_retention": ["3年", "36ヶ月", "36カ月", "36箇月"]
        }
    },
    {
        "id": "long_02",
        "category": "long_context_retrieval",
        "title": "複数システムの障害報告書からの根本原因と影響サービスの特定",
        "prompt": """以下の障害インシデント報告書から、「インシデント#3の根本原因となった設定不備」と「それにより二次被害を受けたサービス名」を明確に抜き出して回答してください。

インシデント#1: [2026-06-10] 決済ゲートウェイタイムアウト。原因は上流プロバイダのBGP経路障害。影響: PaymentService。
インシデント#2: [2026-07-04] 検索機能の遅延。原因はElasticsearchのJVMヒープメモリ枯渇。影響: SearchService, CatalogService。
インシデント#3: [2026-08-15] 通知配信の全停止および注文確定メールの遅延。原因はメッセージブローカー(RabbitMQ)の接続上限設定(max_connections=500)の変更漏れであり、トラフィック急増時にコネクション拒否が発生した。これにより二次被害として注文処理を司るOrderProcessingServiceがワーカーブロックに陥り、さらにユーザー向けWebhook配信を行うWebhookDeliveryServiceがキュー詰まりを起こした。
インシデント#4: [2026-08-20] ログ欠損。原因はFluentbitのバッファオーバーフロー。影響: AnalyticsPipeline。""",
        "eval_type": "incident_needle_rules",
        "expected": {
            "cause_keywords": ["RabbitMQ", "接続上限", "max_connections"],
            "secondary_services": ["OrderProcessingService", "WebhookDeliveryService"]
        }
    },

    # -------------------------------------------------------------
    # 5. Ambiguous Intent & Edge Cases (曖昧な指示・前提確認の適切さ)
    # -------------------------------------------------------------
    {
        "id": "ambig_01",
        "category": "ambiguous_intent",
        "title": "主語や前提が欠けた指示に対する適切な確認と選択肢提示",
        "prompt": """「リセットしたいのでコマンドを教えてください。」""",
        "eval_type": "clarification_check",
        "expected": {
            "clarification_keywords": ["何", "対象", "Git", "データベース", "パスワード", "環境", "どれ", "具体的", "用途"]
        }
    },
    {
        "id": "ambig_02",
        "category": "ambiguous_intent",
        "title": "誤った前提を含む質問に対する訂正と正しい事実の提示",
        "prompt": """「Python 3.12で導入された標準の `async/await` 構文の使い方とサンプルコードを教えてください。」""",
        "eval_type": "premise_correction_check",
        "expected": {
            "correction_keywords": ["3.5", "以前から", "導入され", "3.12ではなく", "従来", "既に"]
        }
    }
]

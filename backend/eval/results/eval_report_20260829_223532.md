# 📊 LLM Evaluation Benchmark Report: Multi-Generation Comparison

- **Execution Timestamp**: 20260829_223532
- **Total Benchmark Cases**: 13 cases
- **Evaluated Models**: gemini-3-flash-preview, gemini-3.5-flash-lite, gemini-3.7-flash, gemini-3.1-pro-preview, gemini-3.5-flash, gemini-3.6-flash

## 1. Category-wise Score Matrix (%)

| Category | `gemini-3-flash-preview` | `gemini-3.5-flash-lite` | `gemini-3.7-flash` | `gemini-3.1-pro-preview` | `gemini-3.5-flash` | `gemini-3.6-flash` |
|:---| :---: | :---: | :---: | :---: | :---: | :---: |
| **`ambiguous_intent`** | 50.0% | 100.0% | 0.0% | 0.0% | 50.0% | 0.0% |
| **`long_context_retrieval`** | 75.0% | 100.0% | 0.0% | 0.0% | 25.0% | 50.0% |
| **`multi_step_reasoning`** | 33.3% | 100.0% | 0.0% | 0.0% | 16.7% | 33.3% |
| **`negative_constraint`** | 100.0% | 88.9% | 0.0% | 0.0% | 100.0% | 100.0% |
| **`structured_output`** | 66.7% | 100.0% | 0.0% | 0.0% | 66.7% | 100.0% |
| **🔥 Overall Average** | **65.4%** | **97.4%** | **0.0%** | **0.0%** | **53.8%** | **61.5%** |
| **⏱️ Avg Latency** | 5.65s | 2.47s | 8.55s | 0.14s | 4.66s | 7.21s |

## 2. Detailed Case Breakdown & Insights

### Case: `struct_01` - ECサイト注文情報のJSON抽出 (`structured_output`)
**Prompt Snippet**: `以下のテキストから注文情報を抽出し、指定されたJSONフォーマットのみを出力してください。Markdownのバッククォート(```json)やその他の説明文は一切含めず、純粋なJS...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 4.175s | ✅ 純粋なJSON文字列として出力されました<br>✅ 有効なJSONとしてパース成功<br>✅ すべての期待フィールド値が一致 |
| `gemini-3.5-flash-lite` | 100% | 1.571s | ✅ 純粋なJSON文字列として出力されました<br>✅ 有効なJSONとしてパース成功<br>✅ すべての期待フィールド値が一致 |
| `gemini-3.7-flash` | 0% | 12.042s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.139s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 100% | 3.347s | ✅ 純粋なJSON文字列として出力されました<br>✅ 有効なJSONとしてパース成功<br>✅ すべての期待フィールド値が一致 |
| `gemini-3.6-flash` | 100% | 5.438s | ✅ 純粋なJSON文字列として出力されました<br>✅ 有効なJSONとしてパース成功<br>✅ すべての期待フィールド値が一致 |

### Case: `struct_02` - エラーログの分類と重大度JSON (`structured_output`)
**Prompt Snippet**: `次のシステムログを解析し、JSON形式で出力してください。JSONのみを出力し前後に解説をつけないでください。

ログ:
"[2026-08-29 22:15:30] [ERROR...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 0% | 0.829s | API Error: 503 UNAVAILABLE (Model High Demand / Capacity Limit) |
| `gemini-3.5-flash-lite` | 100% | 0.959s | ✅ 純粋なJSON文字列として出力されました<br>✅ 有効なJSONとしてパース成功<br>✅ すべての期待フィールド値が一致 |
| `gemini-3.7-flash` | 0% | 0.946s | API Error: 503 UNAVAILABLE (Model High Demand / Capacity Limit) |
| `gemini-3.1-pro-preview` | 0% | 0.156s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 0% | 12.055s | API Error: The read operation timed out |
| `gemini-3.6-flash` | 100% | 7.805s | ✅ 純粋なJSON文字列として出力されました<br>✅ 有効なJSONとしてパース成功<br>✅ すべての期待フィールド値が一致 |

### Case: `struct_03` - 配列とネストを含むAPIレスポンス生成 (`structured_output`)
**Prompt Snippet**: `日本の三大都市（東京、大阪、名古屋）の「都市名」「都道府県」「人口(概算)」「名物3点(配列)」を以下のキー名を持つJSON配列形式で出力してください。Markdownコードブロッ...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 4.608s | ✅ 有効なJSON配列としてパース成功 (要素数: 3)<br>✅ 全要素に必要なキーが存在 |
| `gemini-3.5-flash-lite` | 100% | 8.69s | ✅ 有効なJSON配列としてパース成功 (要素数: 3)<br>✅ 全要素に必要なキーが存在 |
| `gemini-3.7-flash` | 0% | 12.037s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.134s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 100% | 4.928s | ✅ 有効なJSON配列としてパース成功 (要素数: 3)<br>✅ 全要素に必要なキーが存在 |
| `gemini-3.6-flash` | 100% | 8.823s | ✅ 有効なJSON配列としてパース成功 (要素数: 3)<br>✅ 全要素に必要なキーが存在 |

### Case: `neg_01` - 特定文字・キーワードの完全排除要約 (`negative_constraint`)
**Prompt Snippet**: `以下の文章を70文字以上120文字以内で要約してください。
【厳格な禁止ルール】:
1. 回答の中に「AI」「人工知能」「モデル」という単語を1回も使用してはいけません。
2. 漢...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 8.922s | ✅ すべての禁止語を完全に回避しました<br>✅ 文字数制限クリア (100文字 / 許容: 60-130) |
| `gemini-3.5-flash-lite` | 100% | 0.919s | ✅ すべての禁止語を完全に回避しました<br>✅ 文字数制限クリア (104文字 / 許容: 60-130) |
| `gemini-3.7-flash` | 0% | 12.053s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.133s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 100% | 5.641s | ✅ すべての禁止語を完全に回避しました<br>✅ 文字数制限クリア (105文字 / 許容: 60-130) |
| `gemini-3.6-flash` | 100% | 6.204s | ✅ すべての禁止語を完全に回避しました<br>✅ 文字数制限クリア (99文字 / 許容: 60-130) |

### Case: `neg_02` - 医療相談における断定・診断の完全禁止とトリアージ (`negative_constraint`)
**Prompt Snippet**: `ユーザーからの質問に対して、アドバイスを行ってください。
【絶対禁止事項】:
- 「〜です」「〜の病気です」「〜にかかっています」などの診断・断定を行わないこと。
- 具体的な市販...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 5.4s | ✅ 市販薬名の提示を回避<br>✅ 専門医/医療機関への受診を推奨<br>✅ 簡潔さクリア (文数: 3 / 許容: 4以下) |
| `gemini-3.5-flash-lite` | 100% | 1.336s | ✅ 市販薬名の提示を回避<br>✅ 専門医/医療機関への受診を推奨<br>✅ 簡潔さクリア (文数: 3 / 許容: 4以下) |
| `gemini-3.7-flash` | 0% | 1.516s | API Error: 503 UNAVAILABLE (Model High Demand / Capacity Limit) |
| `gemini-3.1-pro-preview` | 0% | 0.139s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 100% | 3.9s | ✅ 市販薬名の提示を回避<br>✅ 専門医/医療機関への受診を推奨<br>✅ 簡潔さクリア (文数: 3 / 許容: 4以下) |
| `gemini-3.6-flash` | 100% | 8.203s | ✅ 市販薬名の提示を回避<br>✅ 専門医/医療機関への受診を推奨<br>✅ 簡潔さクリア (文数: 3 / 許容: 4以下) |

### Case: `neg_03` - 句読点・記号の排除とカタカナ語のみの回答 (`negative_constraint`)
**Prompt Snippet**: `Web開発におけるフロントエンド技術の名称を5つ挙げてください。
【制約】:
- カタカナのみ（半角スペース区切り）で出力すること。
- アルファベット、漢字、ひらがな、句読点（、...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 2.411s | ✅ カタカナ・スペースのみで構成<br>✅ 単語数クリア (5語) |
| `gemini-3.5-flash-lite` | 67% | 0.823s | ❌ カタカナ以外の文字・記号が含まれています: 'HTMLCSSJavaScriptTyp'<br>✅ 単語数クリア (5語) |
| `gemini-3.7-flash` | 0% | 12.05s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.141s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 100% | 3.009s | ✅ カタカナ・スペースのみで構成<br>✅ 単語数クリア (5語) |
| `gemini-3.6-flash` | 100% | 5.328s | ✅ カタカナ・スペースのみで構成<br>✅ 単語数クリア (5語) |

### Case: `reasoning_01` - 在庫回転と発注タイミングの論理計算 (`multi_step_reasoning`)
**Prompt Snippet**: `次の条件から、最終的な「次回発注が必要となる日数（今日から何日後か）」と「発注数量」を計算し、最後の行に `ANSWER: X日後, Y個` という形式で結論のみを記述してください...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 6.414s | ✅ 最終フォーマットに完全合致 (ANSWER:\s*10日後,\s*400個) |
| `gemini-3.5-flash-lite` | 100% | 1.743s | ✅ 最終フォーマットに完全合致 (ANSWER:\s*10日後,\s*400個) |
| `gemini-3.7-flash` | 0% | 12.051s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.127s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 0% | 7.44s | ❌ 計算結果が不一致 |
| `gemini-3.6-flash` | 100% | 9.43s | ✅ 最終フォーマットに完全合致 (ANSWER:\s*10日後,\s*400個) |

### Case: `reasoning_02` - 複数の制約を満たすスケジュール配置問題 (`multi_step_reasoning`)
**Prompt Snippet**: `4人のメンバー（A, B, C, D）の月曜日から木曜日までの当番シフトを1人1日ずつ割り当てます。
以下の条件をすべて満たすシフト表を決定し、最終行に `RESULT: 月=X,...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 0% | 10.11s | ❌ スケジュール制約の推論に失敗 |
| `gemini-3.5-flash-lite` | 100% | 3.178s | ✅ 正確なシフト割り当て結果 (月=A, 火=B, 水=D, 木=C) |
| `gemini-3.7-flash` | 0% | 12.057s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.139s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 50% | 7.683s | ⚠️ 前半の制約(A,B)は合致していますが後半の割り当てが不正 |
| `gemini-3.6-flash` | 0% | 0.146s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |

### Case: `reasoning_03` - 複雑な税率と割引が絡む複数商品の請求計算 (`multi_step_reasoning`)
**Prompt Snippet**: `以下の注文の最終合計金額（税込、端数切捨て）を算出し、最終行に `FINAL_TOTAL: XXXXX円` と出力してください。

内訳:
- 商品A（標準税率10%対象）: 単価...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 0% | 9.746s | ❌ 税抜割引・複数税率・送料の複合計算結果が不一致 |
| `gemini-3.5-flash-lite` | 100% | 3.488s | ✅ 税込合計金額が完全一致 (26,720円) |
| `gemini-3.7-flash` | 0% | 12.046s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.126s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 0% | 0.142s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.6-flash` | 0% | 0.15s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |

### Case: `long_01` - 架空の社内セキュリティ規程からの特定条項抽出 (`long_context_retrieval`)
**Prompt Snippet**: `以下の社内文書を読み、「業務委託先が本番データベースのアクセス権限を申請する際に必須となる承認者の役職」および「アクセスログの最低保管期間」を過不足なく抽出して答えてください。回答...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 50% | 11.122s | ✅ 業務委託DBアクセス承認者を正確に抽出 (['セキュリティ統括責任者', 'CISO', '執行役員'])<br>❌ ログ保管期間の抽出不一致 |
| `gemini-3.5-flash-lite` | 100% | 0.978s | ✅ 業務委託DBアクセス承認者を正確に抽出 (['セキュリティ統括責任者', 'CISO', '執行役員'])<br>✅ DB全クエリログ保管期間(3年間/36ヶ月)を正確に抽出 |
| `gemini-3.7-flash` | 0% | 12.046s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.131s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 50% | 3.652s | ✅ 業務委託DBアクセス承認者を正確に抽出 (['セキュリティ統括責任者', 'CISO', '執行役員'])<br>❌ ログ保管期間の抽出不一致 |
| `gemini-3.6-flash` | 0% | 12.054s | API Error: The read operation timed out |

### Case: `long_02` - 複数システムの障害報告書からの根本原因と影響サービスの特定 (`long_context_retrieval`)
**Prompt Snippet**: `以下の障害インシデント報告書から、「インシデント#3の根本原因となった設定不備」と「それにより二次被害を受けたサービス名」を明確に抜き出して回答してください。

インシデント#1:...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 2.763s | ✅ 根本原因(RabbitMQ接続上限)を特定 (['RabbitMQ', '接続上限', 'max_connections'])<br>✅ 二次被害サービス2件を過不足なく特定 (['OrderProcessingService', 'WebhookDeliveryService']) |
| `gemini-3.5-flash-lite` | 100% | 1.175s | ✅ 根本原因(RabbitMQ接続上限)を特定 (['RabbitMQ', '接続上限', 'max_connections'])<br>✅ 二次被害サービス2件を過不足なく特定 (['OrderProcessingService', 'WebhookDeliveryService']) |
| `gemini-3.7-flash` | 0% | 0.153s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.1-pro-preview` | 0% | 0.145s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 0% | 0.151s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.6-flash` | 100% | 6.048s | ✅ 根本原因(RabbitMQ接続上限)を特定 (['RabbitMQ', '接続上限', 'max_connections'])<br>✅ 二次被害サービス2件を過不足なく特定 (['OrderProcessingService', 'WebhookDeliveryService']) |

### Case: `ambig_01` - 主語や前提が欠けた指示に対する適切な確認と選択肢提示 (`ambiguous_intent`)
**Prompt Snippet**: `「リセットしたいのでコマンドを教えてください。」...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 100% | 6.761s | ✅ 曖昧な質問に対して対象・意図を確認する適切な返答 (['何', '対象', 'Git', '環境']) |
| `gemini-3.5-flash-lite` | 100% | 2.521s | ✅ 曖昧な質問に対して対象・意図を確認する適切な返答 (['何', 'Git', '環境', '具体的']) |
| `gemini-3.7-flash` | 0% | 12.064s | API Error: The read operation timed out |
| `gemini-3.1-pro-preview` | 0% | 0.116s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 0% | 0.117s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.6-flash` | 0% | 12.048s | API Error: The read operation timed out |

### Case: `ambig_02` - 誤った前提を含む質問に対する訂正と正しい事実の提示 (`ambiguous_intent`)
**Prompt Snippet**: `「Python 3.12で導入された標準の `async/await` 構文の使い方とサンプルコードを教えてください。」...`

| Model | Score | Latency | Evaluation Details |
|:---|:---:|:---:|:---|
| `gemini-3-flash-preview` | 0% | 0.154s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash-lite` | 100% | 4.778s | ✅ Python 3.12導入という誤った前提を正しく指摘・訂正 (['3.5', '導入され', '従来']) |
| `gemini-3.7-flash` | 0% | 0.132s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.1-pro-preview` | 0% | 0.145s | API Error: 429 RESOURCE_EXHAUSTED (Free Tier Quota Limit: 0 or Rate Limit) |
| `gemini-3.5-flash` | 100% | 8.545s | ✅ Python 3.12導入という誤った前提を正しく指摘・訂正 (['3.5', '導入され']) |
| `gemini-3.6-flash` | 0% | 12.048s | API Error: The read operation timed out |

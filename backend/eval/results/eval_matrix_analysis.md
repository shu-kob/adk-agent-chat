# 📊 LLM モデル × カテゴリ別 評価ベンチマークマトリクス & 考察レポート (Phase 1 & 2 準拠 / Addendum v4 完全カバレッジ測定版)

本ドキュメントは、`docs/SPECIFICATION.md` 第 5 章および `docs/SPECIFICATION_ADDENDUM_v4.md` に基づき、レート制限対策（指数バックオフリトライ・スロットリング・バースト事前疎通）を適用して**測定カバレッジ 100.0%（欠測 0 件・全 270 試行完了）**で実施した最新の決定論的アサーション評価結果と考察をまとめたものです。

---

## 1. 実行条件と評価環境

- **Run ID**: `20260830_175501`
- **データセット**: `backend/eval/datasets/benchmark_v2.json` (バージョン: `v2.0.0`, 全 30 ケース)
- **試行回数**: 各ケース 3 回試行 (`trials_per_case=3`, 代表値: 中央値 Median)
- **測定カバレッジ**: **100.0% (全モデル・全ケース 30/30 測定完了, 総試行 270/270 成功)**
- **生成パラメータ**: `temperature=0.0`, `seed=42`
- **フォールバック**: `allow_fallback=False` (ADK/API の純粋性能を測定)
- **実行環境**: Vertex AI (`location: global`)
- **総所要時間 / コスト**: 1591.0 秒 (約 26 分 30 秒) / 総コスト: `$0.058933`

---

## 2. カテゴリ別 評価マトリクス (確定版: 欠測なし完全測定)

| 評価カテゴリ | `gemini-3.7-flash` | `gemini-3.5-flash-lite` | `gemini-3.1-pro-preview` |
| :--- | :---: | :---: | :---: |
| **`structured_output`** (厳格JSONスキーマ出力: 10問) | 94.2% (7/10) | **96.8% (8/10)** | 94.2% (7/10) |
| **`negative_constraint`** (禁止単語・文字除外制約: 10問) | 79.7% (6/10) | **88.3% (8/10)** | 84.7% (6/10) |
| **`multi_step_reasoning`** (多段階論理・算術パズル: 10問) | 60.0% (6/10) | **80.0% (8/10)** | 60.0% (6/10) |
| **🔥 総合平均スコア (30問)** | **78.0% (19/30)** | **88.4% (24/30)** | **79.6% (19/30)** |

> 💡 **スコア表記**: `中央値スコア (満点合格ケース数 / 総ケース数)`
> 💡 **Addendum v4 における訂正点**: 前回（初回測定）では `gemini-3.7-flash` で HTTP 429 エラーが多発し `negative_constraint` の 4 問が欠測（未測定）となっていたため見かけ上 91.1% と高騰していましたが、リトライ・スロットリング適用により全問測定した結果、正確な実力値は **79.7%** であることが判明しました。

---

## 3. 失敗分布分析 (スコアばらつき & 満点率・0点率)

| モデル | カテゴリ | 満点率 (1.0) | 0点率 (0.0) | ケース間標準偏差 (stddev) | 特性傾向 |
|:---|:---|:---:|:---:|:---:|:---|
| `gemini-3.7-flash` | `multi_step_reasoning` | 60.0% | 40.0% | 0.516 | 集中型失敗 |
| `gemini-3.7-flash` | `negative_constraint` | 60.0% | 10.0% | 0.331 | 分散型 |
| `gemini-3.7-flash` | `structured_output` | 70.0% | 0.0% | 0.097 | 高安定 |
| `gemini-3.5-flash-lite` | `multi_step_reasoning` | 80.0% | 20.0% | 0.422 | 集中型失敗 |
| `gemini-3.5-flash-lite` | `negative_constraint` | 80.0% | 0.0% | 0.249 | 分散型 |
| `gemini-3.5-flash-lite` | `structured_output` | 80.0% | 0.0% | 0.071 | 高安定 |
| `gemini-3.1-pro-preview` | `multi_step_reasoning` | 60.0% | 40.0% | 0.516 | 集中型失敗 |
| `gemini-3.1-pro-preview` | `negative_constraint` | 60.0% | 0.0% | 0.215 | 分散型 |
| `gemini-3.1-pro-preview` | `structured_output` | 70.0% | 0.0% | 0.097 | 高安定 |

---

## 4. アサーション別 失敗内訳 & 制約違反分析

各モデルがどの制約で不合格となったかを、アサーション単位の失敗内訳から分析します。

### ① `gemini-3.5-flash-lite` (総合スコア: 88.4% — 最優秀)
- **強み**: 
  - 全 3 カテゴリ（`structured_output`: 96.8%, `negative_constraint`: 88.3%, `multi_step_reasoning`: 80.0%）で単独トップを記録。
  - 会議室重複解決、為替計算、総当たりリーグ戦、シフト割当、積載最適化など多段階推論タスクで高い正解率を達成。
- **弱点・失敗アサーション**:
  - `negative_constraint`: 助詞「の」「ノ」の完全排除指示において `forbidden_char__の` / `forbidden_char__ノ` が 3 回失敗。
  - カタカナ排除指示で `no_katakana_check` に 3 回失敗。

### ② `gemini-3.1-pro-preview` (総合スコア: 79.6%)
- **強み**:
  - `structured_output` (94.2%) で高水準を維持。
  - `negative_constraint` では 0 点ケースがなく安定した部分点を獲得 (84.7%)。
- **弱点・失敗アサーション**:
  - `negative_constraint`: 最小文字数制約 (`min_length_check` 8回失敗) や医療免責条項の付与漏れ (`medical_disclaimer_present` 3回失敗)。
  - `multi_step_reasoning`: パターンの完全一致 (`exact_target_pattern_match` 5回)、移動不可判定 (`impossibility_judgment_and_reason` 3回)、税率計算 (`calculation_final_amount_match` 3回) で失点。

### ③ `gemini-3.7-flash` (総合スコア: 78.0%)
- **強み**:
  - `structured_output` (94.2%) で高いスキーマ準拠率。
- **弱点・失敗アサーション**:
  - `negative_constraint` (79.7%): 最小文字数不足 (`min_length_check` 6回失敗)、医療免責漏れ (`medical_disclaimer_present` 3回)、カタカナ混入 (`pure_katakana_check` 3回) が全問測定により判明。
  - `multi_step_reasoning` (60.0%): 移動時間を考慮した旅程プランニング（`impossibility_judgment_and_reason`）および複数税率計算（`calculation_final_amount_match`）で失点。

---

## 5. 運用上の推奨モデル選定

| 用途・シーン | 推奨モデル | 選定理由 |
| :--- | :--- | :--- |
| **通常対話 & API デフォルト** | **`gemini-3.5-flash-lite`** | 総合スコア 88.4% と全カテゴリで最高精度であり、トークン単価が最も低コスト（$0.075/1M in）。コスト対効果が圧倒的に優れる。 |
| **厳格スキーマ・構造化データ出力** | **`gemini-3.5-flash-lite` / `gemini-3.7-flash`** | 厳格 JSON モード時のスキーマ遵守率（96.8% / 94.2%）が高く、実用上のエラーが極めて少ない。 |
| **推論・複合制約タスク** | **`gemini-3.5-flash-lite`** | 現行の多段階推論パズルや否定制約において、flash-lite が flash / pro プレビューよりも高い制約遵守と正解率を示している。 |

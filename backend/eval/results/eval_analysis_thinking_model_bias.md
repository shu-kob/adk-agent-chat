# 考察: なぜ gemini-3.5-flash-lite が上位モデルに勝っているのか

## 結論

**問題設定が簡単すぎるのではない。ベンチマークの測定方法にバグがある。**

`gemini-3.7-flash` と `gemini-3.1-pro-preview` は「思考モデル（Thinking Model）」であり、`max_output_tokens` の予算を **内部推論（thinking tokens）と可視出力（visible output）で共有する**。現在のベンチマークはこの仕様を考慮しておらず、思考モデルの出力が途中で切れた状態で採点している。つまり **flash-lite が優秀なのではなく、flash と pro にハンディキャップを負わせた状態で測定している**。

---

## 根拠: 数値に現れた異常

### 1. 出力トークン数の極端な非対称

30ケース中、trial 0 における可視出力トークンが 50 以下のケース数:

| モデル | 50トークン以下 | 平均利用率 (visible / max) |
|:---|:---:|:---:|
| `gemini-3.7-flash` | **15/30** (50%) | **7.6%** |
| `gemini-3.1-pro-preview` | **17/30** (57%) | **7.2%** |
| `gemini-3.5-flash-lite` | 4/30 (13%) | 28.6% |

flash と pro は `max_output_tokens=1024` のうち平均 7% しか可視出力に使えていない。残りの約93%は**内部思考（thinking tokens）に消費されている**。

### 2. 文の途中で切れている具体例

**reasoning_05（犯人特定論理パズル, 正解: C）**:

| モデル | 可視トークン | 出力内容 | スコア |
|:---|:---:|:---|:---:|
| `gemini-3.7-flash` | 41 | `それぞれの証言を検証してみましょう。（中略）犯人以外の2` | 0% |
| `gemini-3.1-pro-preview` | 41 | `この問題は、条件を一つずつ当てはめていくことで（中略）犯人だけが本当` | 0% |
| `gemini-3.5-flash-lite` | 1020 | （全推論過程を展開し、最後に `犯人: C` を出力） | 100% |

flash と pro は **文が途中で途切れている**。推論を開始しようとした矢先に可視出力の枠を使い切って停止した。「問題を解けなかった」のではなく、**答えを書く欄がなかった**。

### 3. 短い答えで済むケースでは flash/pro も正解している

| ケース | flash | lite | pro | 内容 |
|:---|:---:|:---:|:---:|:---|
| reasoning_07 | ✅ (4 tokens: `優勝: 甲チーム`) | ✅ | ✅ | リーグ戦順位判定 |
| reasoning_08 | ✅ (7 tokens: `水曜夜勤: 佐藤`) | ✅ | ✅ | シフト割当 |
| reasoning_04 | ✅ (9 tokens: `利用可能会議室: 会議室B`) | ✅ | ✅ | 会議室予約 |

内部で十分に思考したうえで、可視出力が短い答えだけで済むケースでは正解できている。思考モデルが「推論能力で劣っている」わけではない。

---

## スコア差の内訳: 5勝2敗23引き分け

30ケース中、flash-lite が flash/pro の**両方**に厳密に勝ったケースは **5件**、負けたケースは **2件**、残り23件は全モデル同点:

### flash-lite が勝った5件

| Case | flash | lite | pro | 勝因 |
|:---|:---:|:---:|:---:|:---|
| reasoning_02 | 0% | 100% | 0% | flash/pro は出力途中で切断。lite のみ「不可能」判定を完遂 |
| reasoning_05 | 0% | 100% | 0% | 犯人特定パズル。flash/pro は結論に到達できず |
| neg_01 | 80% | 100% | 80% | flash/pro は `min_length_check` 失敗（出力が短すぎる） |
| neg_02 | 50% | 100% | 50% | flash/pro は `medical_disclaimer_present` 失敗 |
| struct_09 | 75% | 100% | 75% | flash/pro が `origin: "HND (東京羽田)"` と補足を追加 |

**5件中4件は「出力が短すぎる / 途中で切れている」ことが直接原因。** これは思考トークンが出力予算を圧迫した結果である可能性が高い。

唯一 struct_09 だけは、思考モデルが情報を補足しすぎてフィールド値の完全一致に失敗した別種の問題（over-helpfulness）。

### flash-lite が負けた2件

| Case | flash | lite | pro | 敗因 |
|:---|:---:|:---:|:---:|:---|
| neg_06 | 100% | 50% | 50% | lite がカタカナ語を混入 (`no_katakana_check` 失敗) |
| neg_09 | 67% | 33% | 67% | lite が `の` を混入 (`forbidden_char` 失敗) |

この2件では lite が否定制約を遵守できず、flash/pro のほうが制約を守れている。

---

## 修正すべきこと

### 即時修正: 思考モデルの `thinking_budget` を制御する

`backend/eval/runner.py` の `GenerateContentConfig` で `thinkingConfig` を指定し、**思考トークンに専用の予算を割り当てる**か、**思考を無効化する**必要がある。

```python
# 案A: 思考を無効化して非思考モデルと同条件にする
config = types.GenerateContentConfig(
    temperature=temperature,
    seed=seed,
    max_output_tokens=max_output_tokens,
    system_instruction=DEFAULT_INSTRUCTION,
    thinking_config=types.ThinkingConfig(thinking_budget=0)
)

# 案B: 思考予算を別枠で確保し、可視出力を保護する
config = types.GenerateContentConfig(
    temperature=temperature,
    seed=seed,
    max_output_tokens=max_output_tokens + 4096,  # 思考分を加算
    system_instruction=DEFAULT_INSTRUCTION,
    thinking_config=types.ThinkingConfig(thinking_budget=4096)
)
```

> **案A（思考無効化）** は公平な比較には適するが、思考モデルの本来の能力を測定できない。
> **案B（思考予算別枠）** は各モデルの最大能力を引き出すが、トークン総量が異なるため「コスト対効果」の比較には注意が必要。
>
> **目的に応じて選択すべき。** 「APIバックエンドに組み込む際のコスパ比較」なら案A、「各モデルの推論能力の上限を測る」なら案B。

### 中期的: ベンチマークケースの難易度再検討

上記の修正後に再測定しない限り、「問題が簡単すぎるかどうか」は判断できない。現在の結果は測定方法の欠陥に汚染されている。

ただし、30ケース中23件が全モデル同点（＝天井効果）であることは事実であり、思考トークン問題を修正した後も flash-lite と flash/pro の差が出にくい可能性はある。その場合はケースの高難度化（多段推論のステップ数増加、制約の複合化など）を検討すべき。

---

## まとめ

| 観点 | 判定 |
|:---|:---|
| 「問題設定が簡単すぎる」から lite が勝っている？ | **部分的に正しいが、主因ではない** |
| 主因は何か？ | **思考モデルの `max_output_tokens` 共有仕様に対する未対応（測定バグ）** |
| flash/pro は本当に lite より劣るのか？ | **現時点のデータからは判断不能。** 出力が切断されたケースが多すぎる |
| 次にすべきことは？ | **`thinkingConfig` を設定して再測定。** その結果で初めて公平な比較が可能になる |

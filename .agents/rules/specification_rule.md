# Rule: Specification Maintenance (仕様書同期ルール)

## Mandatory Directive
当リポジトリ内のソースコード（フロントエンド、バックエンド、評価基盤、設定ファイル等）を変更・追加・削除した場合は、必ずプロジェクトルートにある [SPECIFICATION.md](file:///Users/kobuchishu/programing/adk-agent-chat/SPECIFICATION.md) を確認し、最新の仕様と整合するように同期更新を行ってください。

## 対象項目
- API エンドポイントやリクエスト/レスポンススキーマの変更
- 環境変数や設定項目の追加・変更
- エージェントロジックやセッション管理方式の変更
- フロントエンドコンポーネントや状態管理の変更
- 評価基盤（テストケース、採点ロジック、データ出力構造）の変更

<div align="center">

# Agent-Me

**監査可能なマルチエージェント RAG システムを構築・検査・評価。**

Agent-Me は、監査可能なロールベースのマルチエージェント RAG ワークフローのオープンソース参照実装で、バイリンガルの実践的エンジニアリングカリキュラムを備えています。

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> この文書はプロジェクト概要の日本語訳です。完全な技術仕様については、[英語版 README](../../README.md) と <code>docs/</code> を参照してください。

## Agent-Me とは

実行可能な FastAPI + React 実装では、Planner、Researcher、Critic、Writer と任意の Verifier を単一プロセス内で順番に実行します。型付きハンドオフ、検索された根拠、ブロック判断、安全な運用トレース、決定論的評価を検査できます。ローカルのコアパスに有料モデル API は不要です。

## Agent-Me ではないもの

現時点では、分散マルチエージェントランタイム、汎用 Agent SDK、ホスト型企業プラットフォームではなく、事実の正しさも保証しません。Verifier は機械的な出力不変条件を確認するだけです。

## エンジニアリングカリキュラム

カリキュラムは参照実装と同じアーキテクチャを段階的に再構築します。完全版は[英語](../../course/README.md)と[簡体字中国語](../../course/translations/zh-CN/README.md)で提供しています。

## 主な機能

| 項目 | 内容 |
| --- | --- |
| 知識ソース | レビュー・バージョン管理可能な Markdown |
| 検索 | 決定論的なローカル検索と根拠抜粋 |
| 生成 | 任意の OpenAI 互換プロバイダー |
| バックエンド | FastAPI、厳格なスキーマと入力制限 |
| フロントエンド | React、安全なテキスト表示、レスポンシブ UI |
| 国際化 | ブラウザー言語の自動判定と 9 言語 |
| 品質 | Docker Compose、CI、テスト、Lint、型チェック |

## クイックスタート

Docker と Compose プラグインが必要です。

~~~bash
git clone https://github.com/jzjzzzzzzz/agent-me.git
cd agent-me
cp .env.example .env
docker compose up --build
~~~

Web UI は <http://localhost:5173>、API ドキュメントは <http://localhost:8000/docs> で開けます。既定のローカル抽出モードに API キーは不要です。

## カスタマイズ

1. <code>knowledge/example-profile.md</code> を、利用権限のある Markdown 文書に置き換えます。
2. ローカルの <code>.env</code> でアプリ名と説明を設定します。
3. ローカル抽出モードを使うか、OpenAI 互換プロバイダーを設定します。
4. 公開前に根拠となる抜粋を確認し、知識を調整します。
5. 本番シークレットはホスティング環境の Secret Manager で管理してください。

## 国際化

UI は 9 言語に対応します。初回はブラウザーのロケールを使用し、手動選択はブラウザー内に保存されます。未対応言語は英語へフォールバックします。詳しくは[ローカライズガイド](../LOCALIZATION.md)をご覧ください。

## セキュリティとプライバシー

- プロンプトと知識ファイルを信頼できない入力として扱ってください。
- UI は応答を生の HTML ではなくテキストとして表示します。
- ローカル抽出モードは質問や文書を外部へ送信しません。
- このスターターは既定でチャット内容や分析データを永続化しません。
- シークレット、個人通信、規制対象データ、機微な個人情報を知識ディレクトリに置かないでください。

脆弱性は [SECURITY.md](../../SECURITY.md) の手順で非公開報告してください。

## ドキュメント・貢献・ライセンス

[API](../API.md)、[アーキテクチャ](../ARCHITECTURE.md)、[デプロイ](../DEPLOYMENT.md)、[コントリビューションガイド](../../CONTRIBUTING.md)を参照してください。

関連プロジェクト：[Human API](https://github.com/jzjzzzzzzz/human-api)。ライセンスは [MIT](../../LICENSE) です。

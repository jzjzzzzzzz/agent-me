<div align="center">

# Agent-Me

**自分で管理する知識から、透明で根拠のある回答エージェントを構築。**

型付けされた FastAPI バックエンド、React UI、ローカル文書検索、任意の OpenAI 互換プロバイダーを備えた、プライバシー重視のオープンソース基盤です。

[English](../../README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

</div>

> この文書はプロジェクト概要の日本語訳です。完全な技術仕様については、[英語版 README](../../README.md) と <code>docs/</code> を参照してください。

## 無料のハンズオンコース

Agent-Me は、8 レッスンの体系的なコースを第一にした構成です。前提知識、原理、ソースコードの読み方、実行可能なラボ、演習、理解度確認、ポートフォリオ向け最終課題を含みます。完全版は現在、[英語](../../course/README.md)と[簡体字中国語](../../course/translations/zh-CN/README.md)で提供しています。翻訳への貢献を歓迎し、未完成の範囲は[言語対応表](../../course/LANGUAGES.md)に明記します。

## 概要

Agent-Me は Markdown 文書を根拠とする Q&A エージェントを公開するための、小さく監査しやすいフレームワークです。

- **ローカル抽出モード**は外部モデルや API キーなしで動作します。
- **プロバイダーモード**では、検索されたコンテキストと直近の会話だけを、設定した OpenAI 互換エンドポイントへ送信します。
- 回答には根拠となる文書の抜粋を含められます。

公開リポジトリに本番データベース、非公開メモリ、分析記録、認証情報、デプロイ用シークレットは含まれません。

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

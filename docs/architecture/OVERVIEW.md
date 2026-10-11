# アーキテクチャ

```text
Browser → Next.js :3000 → FastAPI :8000 → PostgreSQL
                              │              │
                              │        durable Job/outbox
                              │              ↓
                              └── private storage ← Celery ← RabbitMQ
                                                  ↑
                                           Beat outbox scan
                              Redis: rate limits only
```

APIとworkerは同じドメインモデルを共有するモジュラーモノリスです。`auth`、`media`、`cells`、`collections`（Shelfを含む）、`analysis`、`jobs`、`search`、`storage` に責務を分けています。別サービスへの抽出や空のworkerパッケージは先送りしました。

Webのサーバー状態はTanStack Query、フォームはReact Hook Form/Zod、ページ・検索・開く動画・区間はURLです。Next.jsの同一Originプロキシは動画をストリーム転送し、巨大なアップロード全体をWebメモリーへ読み込みません。共有型は `packages/shared-types`、通信は `packages/api-client` です。

Sourceは元の出所、Mediaは論理的な動画、Assetは元動画等の物理オブジェクトを表します。CellはMediaへの区間参照で、動画を複製しません。整理先は多対多です。Library境界は所有者認可に使用します。共有・共同利用へ拡張する計画はありません。

Jobと解析履歴はPostgreSQLが正本です。コミット後にRabbitMQへ通知し、通知漏れはBeatがJob行をoutboxとして再配信します。行ロックと状態遷移で重複処理を防ぎ、長時間更新されない実行状態をタイムアウトにします。ユーザー操作で最大3回まで再実行できます。取り込みと解析は同じworkerを使用し、重いサブプロセスを2つまで並行実行します。

UI進捗は実行中2秒間隔のpollingを使用します。候補はAnalysisEvent、保存した区間はCellです。解析の結果でユーザーのCellを上書きしません。検索はPostgreSQLのILIKEで始め、ページングを適用します。日本語検索を含む小規模ライブラリ向けで、大規模向けのtrigram/全文索引・意味検索はまだありません。

Storage契約には旧S3実装を残しますが、現在の設定検証はLocalStorageだけを許可し、S3・OIDC・外部DB/キューの設定を拒否します。`sources` のアダプターはYouTube・X・Instagram・TikTokのURLを正規化し、メタデータと参照を保存します。REFERENCEにはカバーAssetを保存できますが、リンク追加だけでは動画AssetやJobを作りません。切り取り時だけ公開動画を一時取得し、認可付きで配信します。このキャッシュは永続Media/Assetやバックアップの対象外です。[ADR 0005](../adr/0005-local-only-contact-and-public-previews.md)を参照してください。

APIはローカルの構造化JSONログ、request ID、DB監査イベントを持ちます。外部テレメトリーやトレース送信を行いません。お問い合わせ用GETは設定されたGitHub窓口のURLだけを返し、文章・ログ・ライブラリデータを送信するAPIは設けません。

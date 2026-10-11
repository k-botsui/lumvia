# Lumvia

**思い出を、あなただけに。** 動画を集め、残したい区間を **Cell** として保存し、あとからその瞬間へ戻れるローカル映像ライブラリです。動画・Cellは **Shelf** へまとめられます。

このリポジトリは **v0.1のソース閲覧目的**で公開します。オープンソースではありません。改変・再配布・実行には権利者の別途許可が必要です。[LICENSE](LICENSE)と[第三者の依存・素材](THIRD_PARTY_NOTICES.md)を確認してください。以下のセットアップは許可された開発・検証環境向けです。

## 主な機能

- MP4/MOVなどの複数動画追加、FFmpegによるプレビュー・サムネイル生成、認証付き再生。
- 残したい区間のCell保存・編集・再生、5分以内のMP4書き出し。
- 動画・CellのShelf整理、名前・色・ヘッダー画像、一括追加・削除、お気に入り・タグ・メモ検索。
- ローカルのシーン切り替わり検出、ジョブ進捗・再試行。
- YouTube・X・Instagram・TikTokの共有URL整理、公式プレーヤー、取得可能な公開動画の期限付き場面プレビュー。
- ローカルパスワード認証、所有者単位の認可、CSRFとOrigin検査、処理・容量・アクセス頻度の上限。

クラウド同期・他者共有・共同利用・人物探索・文字起こしは現行版の対象外です。リンク追加だけでは動画本体を永続保存しません。外部プレーヤー・メタデータ・一時プレビューには配信元への通信が発生します。アップロードした動画の解析はローカルで行います。

## 技術スタックと対応環境

| 層 | 使用技術 |
| --- | --- |
| Web | Next.js 16 / React 19 / TypeScript / TanStack Query / Three.js |
| API | Python 3.13 / FastAPI / SQLAlchemy / Alembic |
| 非同期処理 | Celery / RabbitMQ 4 |
| 保存・制限 | PostgreSQL 17 / ローカルファイル / Redis |
| 映像処理 | FFmpeg / FFprobe |
| 検証 | pytest / Playwright / Ruff / Oxlint / Prettier / Gitleaks |

Node.js 24、pnpm 11.25.0、Python 3.13を使用します。macOSネイティブ起動はApple SiliconとHomebrewを前提とします。Windows 11・Linux・他のMacではDocker Compose方式を使用してください。Dockerの実起動とスマホ実機の検証範囲は[検証記録](docs/development/VERIFICATION.md)に記載しています。

## セットアップと起動

リポジトリを取得したあと、プロジェクト直下で実行します。Homebrewを用意したApple Silicon Mac向けです。

```sh
brew install node pnpm python@3.13 postgresql@17 rabbitmq redis ffmpeg
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r apps/api/requirements.txt
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web build
python3 scripts/run_local.py start
```

初回起動は私的データディレクトリに設定・ランダムな秘密鍵・初期パスワードを生成し、DB migrationと初期アカウント作成を行います。ブラウザーで `http://127.0.0.1:3000` を開き、`ログイン情報を開く.command` で初期アカウントを確認します。初回ログイン後は設定からパスワードを変更してください。

- 起動: `python3 scripts/run_local.py start` または `Lumviaを起動.command`
- 開発モード: 通常版を停止して `python3 scripts/run_local.py start --dev`
- 停止: `python3 scripts/run_local.py stop` または `Lumviaを停止.command`
- 画面変更後: `pnpm --dir apps/web build` を実行して通常版を再起動

Nodeを検出できない場合は `LUMVIA_NODE` に実行ファイルのパスを指定します。停止しても動画・DBは残ります。自動起動サービスは登録しません。

WindowsではPython 3.13とDocker Desktopを用意して `Lumvia-start.cmd`、ログイン情報は `Lumvia-login.cmd`、停止は `Lumvia-stop.cmd` を使用します。Docker Compose v2.20以上向けの[導入・保存先](docs/development/DOCKER.md)を参照してください。

任意の[スマホ用HTTPS構成](docs/development/MOBILE.md)は、同じ私的Wi-Fiから自分のPCを利用します。通常起動でLAN公開は行いません。HTTPS構成でもローカルパスワードで認証し、Secure cookie・CSRF・Origin検査を維持します。スマホ単体のバックエンド・オフライン保存には対応しません。

## 使い方

1. 「追加する」で動画を選ぶか、自作の12秒サンプルを取り込みます。
2. 動画を開き、「Cellを作成」で開始・終了を選び、試聴して保存します。
3. 動画・CellをShelfへまとめ、名前・タグ・メモで探します。
4. 共有リンクは「リンクを貼る」に1行1件、最大20件入力します。

Macの「写真」からJPEGだけが渡る場合は、未編集のオリジナルをMOV/MP4として書き出してから追加します。Live PhotosはMOV部分を使用します。iCloudの動画は本体をダウンロードしてから選んでください。

## 設定と必要な環境変数

`.env.example` は説明用です。通常の起動スクリプトは設定を生成するので、リポジトリ内に `.env` を作る必要はありません。APIは私的保存先の `config.env`、Dockerは `compose.env` を読みます。環境変数はファイルの値を上書きします。

| 変数 | 必須・既定値・用途 |
| --- | --- |
| `DATABASE_URL` | API必須。ローカルPostgreSQL接続。起動時に生成 |
| `SECRET_KEY` | API必須、32文字以上。起動時にランダム生成 |
| `APP_URL` | `http://127.0.0.1:3000`。HTTPS構成では自分の私的IPと8443番 |
| `ENVIRONMENT` | `development`。HTTPS構成は `production`、テストは `test` |
| `LOCAL_NETWORK` | `false`。私的Wi-FiのHTTPS接続のみ明示的に有効化 |
| `BROKER_URL` / `REDIS_URL` | ローカルのキュー・レート制限接続。通常は自動設定 |
| `API_INTERNAL_URL` | WebからAPIへの接続。既定 `http://127.0.0.1:8000` |
| `STORAGE_ROOT` | 私的保存先の `storage/`。永続動画の保存先 |
| `REFERENCE_PREVIEW_ROOT` | 私的保存先の `reference-previews/`。永続保存先と重複不可 |
| `FFMPEG_BIN` / `FFPROBE_BIN` | 既定 `ffmpeg` / `ffprobe` |
| `POSTGRES_PASSWORD` / `RABBITMQ_PASSWORD` | Docker必須。設定スクリプトが生成 |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 初期アカウント作成時のみ必要。起動スクリプトが設定 |
| `SUPPORT_GITHUB_REPOSITORY` | 任意の `owner/repository`。空なら問い合わせ窓口は無効 |

容量・件数・タイムアウト・セッション期間の変数は [.env.example](.env.example) と [Settings](apps/api/app/config.py) を参照してください。S3・OIDC・外部DB/キューは現行設定で拒否します。秘密値をREADME、Issue、ログ添付へ書かないでください。

## データの保存と上限

| OS | 私的データの基点 |
| --- | --- |
| macOS | `~/Library/Application Support/Lumvia/` |
| Windows | `%LOCALAPPDATA%\Lumvia\` |
| Linux | `$XDG_DATA_HOME/lumvia/` または `~/.local/share/lumvia/` |

設定・初期認証情報、DB、動画、プレビュー、ログ、バックアップはソースと分離します。DockerのDB・動画は専用volumeに保存します。通常のWeb待ち受けはloopbackだけです。この構成をインターネットへ公開しないでください。

標準上限は1本256 MiB・60分・4096px、元動画合計10 GiB・500本、Cell合計2,000件・1件5分です。一時公開動画は30分で期限切れとなり、1本32 MB・合計256 MBまでキャッシュします。バックアップは[手順と復元](docs/development/BACKUP.md)を参照してください。バックアップにはDB内の認証・個人データが含まれ得ます。

## ディレクトリ構成

```text
apps/
  api/app/          認証・動画・Cell・Shelf・解析・ジョブのAPI
  api/migrations/   Alembic migration
  web/              Next.jsの画面・同一Origin APIプロキシ
packages/
  api-client/       型付きAPIクライアント
  shared-types/     共有型
infrastructure/docker/  Dockerfile・任意のHTTPSゲートウェイ
scripts/            起動・設定・バックアップ・公開検査
tests/             単体・統合・E2Eテスト
docs/              設計・API・運用・検証記録
```

`marketing/`、`docs/private/`、作業スクリーンショット、私的設定・動画・生成物はGit公開対象外です。詳細は[公開仕様](docs/development/PUBLICATION.md)を参照してください。

## 検証

```sh
.venv/bin/ruff check apps/api scripts tests
.venv/bin/ruff format --check apps/api scripts tests
.venv/bin/python scripts/test.py -q
pnpm --dir apps/web typecheck
pnpm --dir apps/web lint
pnpm --dir apps/web exec prettier --check app components lib proxy.ts next.config.ts .oxlintrc.json
pnpm --dir apps/web build
pnpm --dir apps/web audit
.venv/bin/pip-audit --disable-pip --no-deps -r apps/api/requirements.txt
python3 scripts/check_publication.py
python3 scripts/scan_secrets.py
```

テストは専用の `lumvia_test` DBと `test-storage` を使用し、通常DBへの破壊的fixtureを拒否します。E2Eは明示的な使い捨てアカウントの `LUMVIA_E2E_EMAIL` / `LUMVIA_E2E_PASSWORD` を設定して `pnpm --dir apps/web test:e2e` を実行します。

現在の検証結果・未検証範囲は[検証記録](docs/development/VERIFICATION.md)へ記載します。設計は[アーキテクチャ](docs/architecture/OVERVIEW.md)、[API](docs/api/README.md)、[ADR](docs/adr/)、開発手順は[CONTRIBUTING](CONTRIBUTING.md)、脆弱性報告は[SECURITY](SECURITY.md)を参照してください。

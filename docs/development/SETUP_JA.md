# 開発者向けセットアップと詳細な操作

[日本語README](../../README.md) / [English](../../README.en.md)

このページはソースコードから起動する開発者・許可された保守担当者向けです。配布アプリの利用者が実行する手順ではありません。Mac配布アプリはPython等を同梱し、データを `~/Library/Application Support/Lumvia Desktop/` に保存します。以下の保存先表は開発・Docker構成の説明です。

## 技術スタックと対応環境

| 層         | 使用技術                                                       |
| ---------- | -------------------------------------------------------------- |
| Web        | Next.js 16 / React 19 / TypeScript / TanStack Query / Three.js |
| API        | Python 3.13 / FastAPI / SQLAlchemy / Alembic                   |
| 非同期処理 | Celery / RabbitMQ 4                                            |
| 保存・制限 | PostgreSQL 17 / ローカルファイル / Redis                       |
| 映像処理   | FFmpeg / FFprobe                                               |
| 検証       | pytest / Playwright / Ruff / Oxlint / Prettier / Gitleaks      |

Node.js 24、pnpm 11.25.0、Python 3.13を使用します。macOSネイティブ起動はApple SiliconとHomebrewを前提とします。他のOS向けにはDocker Compose構成があります。Windowsのスタンドアロン配布・実行は未実装・未検証です。以下のWindowsコマンドはPython・Dockerを導入する開発構成の手順で、一般利用の完成アプリではありません。Dockerの実起動とスマホ実機の検証範囲は[検証記録](../../docs/development/VERIFICATION.md)に記載しています。

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

WindowsではPython 3.13とDocker Desktopを用意して `Lumvia-start.cmd`、ログイン情報は `Lumvia-login.cmd`、停止は `Lumvia-stop.cmd` を使用します。Docker Compose v2.20以上向けの[導入・保存先](../../docs/development/DOCKER.md)を参照してください。

任意の[スマホ用HTTPS構成](../../docs/development/MOBILE.md)は、同じ私的Wi-Fiから自分のPCを利用します。通常起動でLAN公開は行いません。HTTPS構成でもローカルパスワードで認証し、Secure cookie・CSRF・Origin検査を維持します。スマホ単体のバックエンド・オフライン保存には対応しません。

## 使い方

1. 「追加する」で動画を選ぶか、自作の12秒サンプルを取り込みます。
2. 動画を開き、「Cellを作成」で開始・終了を選び、試聴して保存します。
3. 動画・CellをShelfへまとめ、名前・タグ・メモで探します。
4. 共有リンクは「リンクを貼る」に1行1件、最大20件入力します。

Macの「写真」からJPEGだけが渡る場合は、未編集のオリジナルをMOV/MP4として書き出してから追加します。Live PhotosはMOV部分を使用します。iCloudの動画は本体をダウンロードしてから選んでください。

## リンク集の共有・読み込み

ライブラリやShelfの「リンク集を共有」「このShelfを共有」で確認画面を開きます。選択モードで選んだ項目だけの共有も可能です。外部リンク・タイトル・タグ・お気に入り・Cellの区間・Shelf構成を含み、アップロードした動画本体、認証情報、ローカルパスは含めません。カバー画像とShelfヘッダーは、共有する権利・個人情報を確認して「画像も含める」を選んだ場合だけ、小さなJPEGとしてTXT内に格納します。画像のEXIF等は除去します。メモとShelfの説明は初期状態で除外します。

内容と除外項目を確認し、共有してよいことにチェックを入れると `lumvia-links.txt` を保存できます。UTF-8のJSONデータを格納したテキストファイルで、実行コードや圧縮ファイルではありません。メール・LINE等ではファイルを添付し、受け取った人は「リンク集を読み込む」でファイルを選んで確認・追加します。全文のコピー・貼り付けも可能です。短いリンク集は「SNS用URLをコピー」で、そのURLをXなどへ投稿できます。受信者は公開ページからファイルを保存します。データはURLのフラグメント内に格納され、窓口サーバーには保存しません。URLを知っている人は内容を閲覧できます。2000文字を超えるリンク集はファイルで渡すか、利用者が用意したファイルの公開URLを投稿します。送信先の添付制限・文字数制限・セキュリティ判定を回避する仕組みではありません。

同じ動画・投稿のリンクはURL表記違いを正規化して再利用し、同じ区間のCellも再利用します。既存のタイトル・タグ・メモは上書きしません。同じリンク集の再読み込み・同時送信でも二重登録しません。画像付きファイルは新形式v2、画像なしはv1です。v2の読み込みには対応した更新版が必要です。既存のカバー・ヘッダーは上書きせず、画像がない項目へ追加します。新しいShelfと同名の既存Shelfの内容が異なる場合は名前を分けて保存します。削除した項目は同じファイルから再追加できます。読み込み時には外部サイトへ自動接続せず、動画や画像は取得しません。

リンク集のバックアップにも使えますが、アップロード動画や画像を含む完全バックアップではありません。完全バックアップは[別の手順](../../docs/development/BACKUP.md)を使用してください。形式・上限・復元の範囲は[リンク集の仕様](../../docs/development/LINK_SHARING.md)を参照してください。

## 設定と必要な環境変数

`.env.example` は説明用です。通常の起動スクリプトは設定を生成するので、リポジトリ内に `.env` を作る必要はありません。APIは私的保存先の `config.env`、Dockerは `compose.env` を読みます。環境変数はファイルの値を上書きします。

| 変数                                      | 必須・既定値・用途                                                        |
| ----------------------------------------- | ------------------------------------------------------------------------- |
| `DATABASE_URL`                            | API必須。ローカルPostgreSQL接続。起動時に生成                             |
| `SECRET_KEY`                              | API必須、32文字以上。起動時にランダム生成                                 |
| `APP_URL`                                 | `http://127.0.0.1:3000`。HTTPS構成では自分の私的IPと8443番                |
| `ENVIRONMENT`                             | `development`。HTTPS構成は `production`、テストは `test`                  |
| `LOCAL_NETWORK`                           | `false`。私的Wi-FiのHTTPS接続のみ明示的に有効化                           |
| `BROKER_URL` / `REDIS_URL`                | ローカルのキュー・レート制限接続。通常は自動設定                          |
| `API_INTERNAL_URL`                        | WebからAPIへの接続。既定 `http://127.0.0.1:8000`                          |
| `STORAGE_ROOT`                            | 私的保存先の `storage/`。永続動画の保存先                                 |
| `REFERENCE_PREVIEW_ROOT`                  | 私的保存先の `reference-previews/`。永続保存先と重複不可                  |
| `FFMPEG_BIN` / `FFPROBE_BIN`              | 既定 `ffmpeg` / `ffprobe`                                                 |
| `POSTGRES_PASSWORD` / `RABBITMQ_PASSWORD` | Docker必須。設定スクリプトが生成                                          |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD`          | 初期アカウント作成時のみ必要。起動スクリプトが設定                        |
| `SUPPORT_GATEWAY_URL`                     | 運営側のCloudflare窓口のHTTPS URL。トークンはアプリに設定しない           |
| `SUPPORT_GITHUB_REPOSITORY`               | 既定 `k-botsui/lumvia`。共通窓口からIssue投稿。明示的に空へ設定すると無効 |

容量・件数・タイムアウト・セッション期間の変数は [.env.example](../../.env.example) と [Settings](../../apps/api/app/config.py) を参照してください。S3・OIDC・外部DB/キューは現行設定で拒否します。秘密値をREADME、Issue、ログ添付へ書かないでください。

## データの保存と上限

| OS      | 私的データの基点                                         |
| ------- | -------------------------------------------------------- |
| macOS   | `~/Library/Application Support/Lumvia/`                  |
| Windows | `%LOCALAPPDATA%\Lumvia\`                                 |
| Linux   | `$XDG_DATA_HOME/lumvia/` または `~/.local/share/lumvia/` |

設定・初期認証情報、DB、動画、プレビュー、ログ、バックアップはソースと分離します。DockerのDB・動画は専用volumeに保存します。通常のWeb待ち受けはloopbackだけです。この構成をインターネットへ公開しないでください。

標準上限は1本2 GiB・60分・4096px、元動画合計10 GiB・500本、Cell合計2,000件・1件5分です。一時公開動画は30分で期限切れとなり、1本32 MB・合計256 MBまでキャッシュします。バックアップは[手順と復元](../../docs/development/BACKUP.md)を参照してください。バックアップにはDB内の認証・個人データが含まれ得ます。

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

`marketing/`、`docs/private/`、作業スクリーンショット、私的設定・動画・生成物はGit公開対象外です。詳細は[公開仕様](../../docs/development/PUBLICATION.md)を参照してください。

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

現在の検証結果・未検証範囲は[検証記録](../../docs/development/VERIFICATION.md)へ記載します。設計は[アーキテクチャ](../../docs/architecture/OVERVIEW.md)、[API](../../docs/api/README.md)、[ADR](../../docs/adr/)、開発手順は[CONTRIBUTING](../../CONTRIBUTING.md)、脆弱性報告は[SECURITY](../../SECURITY.md)を参照してください。

## お問い合わせ

設定の「お問い合わせ」で件名と内容を入力し、「送信」でGitHub Issueを作成します。利用者のGitHubログインは不要です。送信する文章は公開され、動画・写真・ログ・ライブラリは添付しません。運営側の無料Cloudflare窓口の準備・公開が必要です。[作成・接続・保存の範囲と現在の準備状況](../../docs/development/SUPPORT.md)を参照してください。

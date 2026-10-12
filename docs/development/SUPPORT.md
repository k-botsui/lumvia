# ログイン不要のお問い合わせ窓口

利用者の操作は「お問い合わせ」→件名・内容を入力→「送信」です。GitHubアカウント、トークン、コピー・貼り付けは不要です。成功後にIssue番号とリンクを表示します。

投稿先は `k-botsui/lumvia`。Lumvia APIからCloudflare Workersの共通窓口へ問い合わせ文を渡し、窓口が運営者の認証でGitHub Issueを作成します。GitHubの投稿者は運営側のアカウントになります。

## 運営者が一度だけ行う準備

### 1. Cloudflare無料アカウントを作る

1. [Cloudflare登録ページ](https://dash.cloudflare.com/sign-up)を開きます。
2. メールアドレスとパスワードで登録し、確認メールからメールアドレスを認証します。
3. ダッシュボードへログインします。
4. Workersは **Free** を使います。Paidへの変更、クレジットカード登録、独自ドメイン購入は不要です。この窓口にはCloudflareの `workers.dev` URLを使用します。

Workers FreeとSQLiteのDurable Objects Freeを使用します。無料枠を超えた処理は失敗し、有料プランへ自動変更する構成にはしません。登録画面で有料契約が表示された場合は進めず、Freeであることを確認してください。[Workers料金](https://developers.cloudflare.com/workers/platform/pricing/) / [Durable Objects料金](https://developers.cloudflare.com/durable-objects/platform/pricing/)。

### 2. GitHubに投稿用の認証情報を作る

[GitHubのFine-grained tokens](https://github.com/settings/personal-access-tokens)でトークンを作成します。

- Token name: `Lumvia support`
- Resource owner: `k-botsui`
- Repository access: **Only select repositories** → **lumviaだけ**
- Repository permissions: **Issues: Read and write**。Metadataの読み取りは自動付与されます。
- 有効期限を設定し、期限前に更新します。リポジトリ全体を変更できるclassic tokenは使いません。

トークンの値はチャット、Git、README、Lumvia利用者へ渡しません。Cloudflare Workerの **Secret** `GITHUB_TOKEN` にだけ設定します。[GitHub公式手順](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)。

### 3. 窓口を公開する

実装は `infrastructure/support-worker/` にあります。アカウント準備後、運営者の環境で以下を実行します。認証時の確認は運営者が行います。

```sh
pnpm --dir infrastructure/support-worker install --frozen-lockfile
pnpm --dir infrastructure/support-worker exec wrangler login
pnpm --dir infrastructure/support-worker deploy
pnpm --dir infrastructure/support-worker exec wrangler secret put GITHUB_TOKEN
```

`secret put` の入力欄かCloudflareダッシュボードのSecret欄へ、運営者自身がトークンを入力します。Secret設定前は窓口は送信を受け付けません。`SupportInbox` はSQLite-backed Durable Objectとして作成されます。

Cloudflareアカウントが既にPaidの場合は、無料枠の説明だけで無課金を保証しないため、Free専用のアカウント・プランを確認してから公開してください。

### 4. Lumviaへ接続する

公開されたHTTPSのWorker URLを、運営側の `SUPPORT_GATEWAY_URL` へ設定します。例は実際のURLに置き換えます。

```dotenv
SUPPORT_GITHUB_REPOSITORY=k-botsui/lumvia
SUPPORT_GATEWAY_URL=https://lumvia-support.<account>.workers.dev
SUPPORT_OPERATOR_DELIVERY=false
```

公開URLは秘密情報ではないため、配布版では既定値にできます。トークンはLumvia側へ設定しません。接続後はアプリを再起動し、件名と本文だけの公開テストIssueで送信・表示を確認します。公開テストは運営者が内容を確認して行います。

## 送信・保存・制限

GitHubへ送るのは入力した件名・本文だけです。動画、写真、ライブラリ、メールアドレス、ログ、Lumviaの認証情報は自動添付しません。PublicのIssueは公開されるため、入力文に個人情報・秘密情報を含めないでください。

草稿は画面内だけで保持します。ローカルDBと窓口には送信ID、HMAC、状態、Issue番号・URLを保存し、本文は保存しません。窓口の送信記録は7日、IPは日別HMACにして制限判定のみに使い、原文IPは保存しません。Cloudflare自体のネットワーク処理・保持はサービスの方針に従います。アプリのバックアップにはローカル送信記録が含まれます。

窓口はIPごと3回/時、全体50回/日、本文10,000文字、HTTP本文45,000バイトまでです。同じ送信IDの再送はIssueを増やしません。通信失敗で作成済みか不明な場合、自動再送を止めて誤った重複投稿を防ぎます。草稿はコピーできます。窓口の投稿制限・無料枠に達した場合はエラーとして通知します。

通常の利用者向けは共通窓口方式だけです。運営者のローカル動作確認用に `SUPPORT_OPERATOR_DELIVERY=true` で、そのPCのGitHub CLIを使用する経路もあります。初期状態はfalseで、配布版では有効化しません。運営者のGitHub認証やトークンを配布物に含めないでください。

## 現在の状態

共通窓口のコード・テスト・配布ビルドは準備済みです。Cloudflareアカウントはまだないため、Workerの本番公開、GitHub Secretの設定、配布用の既定URL、共通窓口での実投稿は未完了です。

# 0007: ログイン不要の共通問い合わせ窓口

採用: 2026-10-12。利用者が件名・本文を入力して「送信」するだけでGitHub Issuesに掲載する。利用者自身のGitHub認証を要求せず、運営者のCloudflare Workers共通窓口が投稿する。ADR 0005の手動コピー・投稿だけという制限を更新する。

Workers FreeとSQLite-backed Durable Objectsを使用する。トークンは対象リポジトリのIssues書き込みだけを許可したfine-grained PATをWorker Secretへ保管し、LumviaやGitには配布しない。窓口の既定リポジトリは運営者設定で固定し、クライアントが変更できない。

ローカルAPIは認証・CSRF・Origin・レート制限を維持し、件名・本文・UUIDをHTTPSの固定窓口へ渡す。窓口は投稿頻度・容量を制限し、同一UUIDをDurable Objectのtransactionで予約して重複を防ぐ。入力文は保存せず、HMACと送信結果のみを記録する。GitHubへは入力した件名・本文だけを渡す。送信結果不明の場合は自動再送しない。

運営者のMacでの動作確認に限り、明示的な非公開設定でPCのCLI認証を利用できる。配布版では無効にし、共通窓口を使う。アカウント作成・Secret設定・無料プラン確認・本番公開後に、既定URLと実投稿検証を完了する。

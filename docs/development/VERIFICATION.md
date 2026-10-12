# 公開準備版の検証

この文書は当時の監査・検証記録です。2026年10月12日に利用条件を個人の私的・非商用利用へ変更しました。現在の条件はルートの[LICENSE](../../LICENSE)と[README](../../README.md)に従います。
実施日: 2026-10-10（JST）。対象はgithub_openの公開準備版です。過去の個別作業記録・スクリーンショットは非公開の `docs/private/` 等へ分け、以前の検証結果を現行版の保証として扱いません。

## 今回の結果

| チェック | 結果 |
| --- | --- |
| 全バックエンドテスト | 137 passed。専用PostgreSQLとtest-storageを使用 |
| 私的HTTPSの認証回帰テスト | パスワードログイン、Secure/HttpOnly/SameSite cookie、認証済み操作、CSRF拒否、異なるOrigin拒否、ログアウト後失効を確認 |
| Ruff lint / format | 成功 |
| Web lint | Oxlintで成功。React Hooks・TypeScript・Next.js・アクセシビリティの検査を実施 |
| TypeScript / Prettier / Next.js本番ビルド | すべて成功 |
| 公開ファイル検査 / Gitleaks | 成功。インデックスが最新版と一致、秘密情報検出0 |
| 文書リンク・公開メディアのタグ | 公開対象へのローカルリンクを確認。アイコンのEXIF0、サンプル動画に個人名・作業パスなし |
| Web全依存監査 | 既知の脆弱性0。開発依存も対象 |
| Python固定依存監査 | 既知の脆弱性0 |

## 公開用の変更

- `eslint-config-next` 経由の脆弱な `braces@3.0.3` を除去し、Oxlint 1.87.0へ移行。依存監査の失敗を無視するCI設定を削除。
- productionでもローカルパスワードを使用。HTTPS、Secure cookie、CSRF、Origin、Library認可を維持。外部ログインは無効。
- 不明な `ENVIRONMENT` を拒否。
- 公開LICENSEをソース閲覧のみへ明確化。第三者依存の許諾を別扱いとして一覧を記録。
- marketing、作業画像、参考ブランド画像、過去の引き継ぎ資料、環境・ログ・認証情報・生成物をGit公開対象から除外。
- 公開文書のローカルユーザー名・絶対パスを除去し、READMEを第三者向けに再構成。
- Gitインデックスと作業内容の一致、私的ファイル、ローカルパスを検査する公開ゲートを追加。
- 秘密情報検査はインデックスと全ローカルblobを対象に実行し、CIは全履歴も検査。

OxlintのReact Hooks検査は有効です。独自のスクロール領域、二次元の画像移動、モバイルダイアログの条件付きroleについて、静的な要素分類では表現できないため該当ファイルのイベント・tabIndex規則を限定して除外しています。roleの代わりにタグを推奨するスタイル規則は無効です。利用者の動画へ架空の字幕trackは挿入せず、字幕対応は現行版の未実装機能としてmedia-has-caption規則を除外しています。

## 検証の限界

- Dockerデーモンが監査環境にないため、コンテナービルド・実起動・イメージ脆弱性検査は未実施。
- Windows実機、iPhone/AndroidのCA導入と私的Wi-Fi実接続は未実施。HTTPS認証のAPI回帰テストと接続構成の静的検査は実施。
- 今回はブラウザーE2Eを再実行していません。長時間・大規模動画の性能保証はありません。
- Authlib/Starletteのhttpx非推奨警告が2件あります。テストは通過しています。互換性を確認した上で将来の依存更新へ対応します。
- 公開準備時点でGitは初回コミット前。存在するblobは検査しましたが、別フォルダーのコピー元・削除済み別履歴は対象外です。
- GitHubのリポジトリ作成、Public化、push、デプロイは実施していません。作成後はPrivate vulnerability reporting、secret scanning、push protectionを有効化し、CI結果を確認してください。

## 2026-10-12 お問い合わせの共通窓口

バックエンド全151テスト、Workerの7テスト、Ruff、Web型検査・Oxlint、本番ビルド、Wranglerのdry-runが成功。Worker依存監査の検出は0。匿名投稿、内容限定、認証・CSRF・Origin、重複防止、IP別・日別制限、本文変更、未接続、結果不明を検証しました。

運営者のMacは既存のGitHub認証を使う非公開の運営用設定で動作確認します。配布用はこの経路を無効とし、Cloudflareの共通窓口を使います。Cloudflareアカウントが未作成のため、共通窓口の本番公開・Secret設定・配布URLは未完了です。公開テストIssueは自動作成していません。

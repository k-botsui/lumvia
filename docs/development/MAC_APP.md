# Macアプリの配布と検証

Mac版は開発用ソフトを導入していない利用者向けです。Intel版とApple Silicon版を用意し、macOS 12 Monterey以降をビルド対象にします。Monterey 12.7.6のIntel Macは互換性検証機の一つで、そこだけに対応する製品にはしません。OSごとの動作確認結果と未確認項目はリリース本文に明記します。Windows・Linux用のインストーラーはこのMac版には含みません。

## 利用者の操作

1. GitHubのReleasesで、自分のMac用のLumviaをダウンロードします。
2. ZIPを開き、Lumvia.appを「アプリケーション」に移動します。
3. Lumvia.appを開きます。初回の準備とローカルのログインはアプリが行います。

Python・Node.js・Homebrew・Docker・データベースの個別インストール、ターミナル操作、GitHubアカウントは不要です。公開済みリリースがない場合は、まだこの配布方法では入手できません。Code → Download ZIPは開発用のソースで、完成したMacアプリとは異なります。

**TESTと記された配布物はAppleのDeveloper IDによる署名・公証がない検証版です。** ダウンロードした検証版はmacOSにブロックされることがあります。Monterey検証機では「壊れているため開けません」で拒否され、通常の「このまま開く」では進めませんでした。個別の検証時に当該アプリの隔離属性を解除しましたが、一般利用者向けの導入方法には採用しません。Gatekeeper全体は無効化しません。一般向けの簡単な初回起動を完成させるにはDeveloper IDによる署名・公証が必要です。

## データと終了

Macアプリのデータは、ユーザーのLibrary内のApplication Support / Lumvia Desktopに保存します。開発用Lumviaの保存先とは別です。アプリを交換・終了してもデータを削除しません。初回のログイン情報はここに生成し、ユーザー本人だけが読める権限にします。外部アカウントの情報やGitHubトークンをアプリに含めません。

サービスは127.0.0.1にだけ接続し、起動ごとに空いているポートを選びます。ログイン項目やシステムサービスは登録しません。アプリ終了時には、そのアプリが起動したプロセスだけを終了します。

共有用のリンク集は、動画ファイルやヘッダー画像を含む完全なバックアップではありません。完全なデータ保全には、Lumviaを終了して保存フォルダー全体をバックアップしてください。開発環境のデータをMacアプリへ移す自動移行はまだありません。

## 開発・配布担当者のビルド

利用者のMacでは実行しません。ビルド側にはXcode Command Line Tools、Python 3.13、インターネット接続が必要です。Node.js 22とpnpm 11.25.0はビルド時に取得します。

```sh
python3 packaging/macos/build.py --arch arm64
python3 packaging/macos/build.py --arch x86_64
```

Intel版はIntel環境、Apple Silicon版はApple Silicon環境でビルドする方法を基本とします。ダウンロード元とSHA-256はruntime-lock.jsonで固定し、不一致なら停止します。依存の更新時には脆弱性・対応OS・ライセンスを確認してロックを更新します。

Node.js 22とポータブルPython、ソースからmacOS 12向けにビルドしたPostgreSQL・Valkey・LGPL構成のFFmpegを同梱します。Next.jsの画面は事前にビルドします。Mac版の処理はPostgreSQLの永続キューを直接読む最大2並列の実行器を使い、RabbitMQやErlangは同梱しません。開発・コンテナー環境のCelery構成は維持します。

生成物はdistに置き、Git管理しません。Macアプリと、対応するFFmpeg等のソースZIPを一緒に配布してください。Mach-Oの最低OS・アーキテクチャ・同梱外ライブラリへの依存、コード署名の整合性を検査します。ad-hoc署名の検証成功はAppleの公証やGatekeeperの通過を意味しません。

一般向け配布前の確認：

- IntelとApple Siliconの両方で、開発用ソフトなしの起動・終了・再起動を確認する。
- Monterey検証機と新しいmacOSで、リンク・動画・Cell・Shelf・共有の保存と読み込み、ファイル選択とダウンロードを確認する。
- 検証データの永続化、処理中の終了、二重起動、ポート競合、アプリ交換後のデータ維持を確認する。
- 同梱ライセンス、対応ソース、個人情報・秘密情報の不在を確認する。
- Developer ID署名・公証とダウンロード後の初回起動を確認する。

## 一次資料

- [Node.js 22の対応プラットフォーム](https://github.com/nodejs/node/blob/v22.x/BUILDING.md)
- [Apple Developer ID](https://developer.apple.com/developer-id/)
- [FFmpegの配布条件](https://ffmpeg.org/legal.html)
- [PostgreSQLのライセンス](https://www.postgresql.org/about/licence/)
- [Valkeyのライセンス](https://valkey.io/topics/license/)

## 2026-10-12の実機フィードバック

Monterey 12.7.6 Intel実機で、ブラウザー経由の動画追加・再生、Cell作成、Shelf作成、再起動後のデータ保持を利用者が確認しました。初版のアプリ内画面は読み込み中で停止しました。改訂版はWebKit自身で認証・cookie設定・認証確認を実行してから画面を再読み込みし、ローカル通信をインターネット接続判定で待機させません。「表示 → 画面を再読み込み」も設けます。実機での再確認は別途必要です。

各サービスの起動ログは現在の起動ごとに更新します。ポートは衝突を避けるため毎回変更できますが、通常利用で利用者が入力する必要はありません。動画カバーは好きな場面から画像を作成して保存できます。共有画面のOS共有メニューは削除し、ファイル保存・データコピー・SNS用URLに統一します。

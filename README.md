# Lumvia

**動画とリンクを、ひとつのローカルライブラリに。**

日本語 · [English](README.en.md) · [ダウンロード](https://github.com/k-botsui/lumvia/releases) · [使い方](#使い方)

Lumviaは、自分の動画とYouTube・X・Instagram・TikTokなどのリンクを整理するデスクトップアプリです。動画の好きな区間を **Cell** として保存し、動画やCellを **Shelf** にまとめて、あとから見返せます。

## トレーラー

<video src="https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Trailer-V7.mp4" controls width="960" poster="https://raw.githubusercontent.com/k-botsui/lumvia/main/demo/lumvia-trailer-v7-poster.jpg"></video>

[トレーラーを開く（28秒・60fps）](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Trailer-V7.mp4)

[映像・音楽のクレジット](demo/README.md)

## ダウンロード

アプリは **GitHub Releasesだけで配布**します。別サイトでの登録やGitHubへのログインは不要です。

**現在のMac版は未公証のTEST版です。macOSが起動を拒否する場合があります。「誰でも解凍して開くだけ」で使える正式版は、まだ完成していません。Windows版も準備中です。**

| お使いのパソコン                     | 配布状況・ダウンロード                                                                                                                                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mac — Apple Silicon（Apple製チップ） | [TEST版ZIP](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-AppleSilicon-TEST.zip) · [DMG](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-AppleSilicon-TEST.dmg) |
| Mac — Intel                          | [TEST版ZIP](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-Intel-TEST.zip) · [DMG](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Mac-Intel-TEST.dmg)               |
| Windows                              | デスクトップ配布版は準備中です。Mac用ZIPでは起動できません。                                                                                                                                                                          |

Macの種類は ** → このMacについて → チップ／プロセッサ** で確認できます。`Source code (zip)` と `Code → Download ZIP` はプログラムのソースコードで、完成したアプリではありません。通常利用では上のOS別ファイルを選んでください。

### ZIPを解凍したら

1. 解凍した中の **Lumvia（`Lumvia.app`）** を確認します。
2. 普段使う場合は「アプリケーション」へ移してから開きます。DMGの場合も、Lumviaを「アプリケーション」へドラッグします。
3. 開き方に迷った場合は、このページとリリースの説明を確認してください。

**同梱案内：** Mac TEST 7のZIPはOS・CPU名の付いたフォルダーにまとめ、**`00_はじめに_READ_ME_FIRST.html`** とTXTで日本語・英語の起動手順を読めます。ソースコードZIPには [`00_START_HERE.html`](00_START_HERE.html) とTXTを同梱しています。

Mac版にはPython・Node.js・データベース・FFmpegを同梱しています。利用者が開発ツールを入れたり、コマンドやURLを入力したりする必要はありません。現在のTEST版がmacOSに拒否された場合は、保護設定を変更せず、[リリースの説明](https://github.com/k-botsui/lumvia/releases/tag/v0.2.0-mac-test.7)を確認してください。

### 検証範囲

Mac両版の同梱サービスと基本操作はテストしています。ローカルのIntel版実行はRosettaでの検証です。macOS 12以降はビルド対象で、全OSの動作保証ではありません。クリーンなMacで実ダウンロードした後の通常起動、Windowsの導入・動作は未確認です。[Mac版の詳細](docs/development/MAC_APP.md)

## できること

- **動画・リンクを保存** — 自分の動画と外部リンクを一覧で管理。
- **Cellを作成** — 好きな区間を保存・編集・再生し、5分以内のMP4に書き出し。
- **Shelfで整理** — 動画・Cellをまとめ、カバー・色・タグ・メモ・お気に入りで探す。
- **リンク集を共有** — 内容を確認してTXTに書き出し、別のLumviaへ読み込み。
- **リンクを一斉点検** — オンライン時に到達状態を確認。切れたと再確認できたリンクは、関連CellとShelfへの登録を確認してまとめて削除。

通信エラー・ログイン制限などは、削除できる「リンク切れ」として扱いません。オフライン時は点検と、この点検結果からの削除を実行しません。外部動画の一時プレビューは配信元・取得形式・同梱codecの対応範囲に依存します。

## 使い方

1. 「追加する」から動画を選ぶか、共有リンクを貼り付けます。
2. 動画を開き、「Cellを作成」で保存したい区間を選びます。
3. 動画・CellをShelfへ追加し、名前・タグ・メモで探します。
4. リンク集を渡す場合は「リンク集を共有」で内容を確認し、受け取った側は「リンク集を読み込む」を選びます。

[リンク集の形式と共有範囲](docs/development/LINK_SHARING.md) · [詳細な操作と開発者向け手順](docs/development/SETUP_JA.md)

## データとプライバシー

追加した動画・Cell・Shelfは自分のパソコンに保存します。Mac配布アプリの保存先は `~/Library/Application Support/Lumvia Desktop/` です。アプリの交換では、このデータを削除しません。完全バックアップは、アプリを終了して保存先全体を保全してください。リンク集のTXTは動画本体を含む完全バックアップではありません。

外部プレーヤー・リンクのメタデータ・一時プレビュー・リンク点検には、配信元などへの通信が必要です。リンク追加だけで動画本体を永続保存することはありません。リンク集の画像・メモ等は共有画面で確認できます。アップロードした動画本体や認証情報を、リンク集に含めません。

## 利用条件

このリポジトリは **個人の私的・非商用利用を無料で許可**しています。オープンソースではありません。自分が所有・管理する端末へのダウンロード、インストール、未改変ソースのビルド・実行、私的バックアップができます。設定変更や初期認証情報の生成も可能です。**プログラムの改変・再配布、商用利用、勤務先・組織での利用、他者へのサービス提供には別途許可が必要**です。[LICENSE](LICENSE)と[第三者の依存・素材](THIRD_PARTY_NOTICES.md)を確認してください。自分の動画・写真・メモや、それらから作成した出力の権利は、このライセンスでは制限しません。

## 開発・技術資料

[開発セットアップ（日本語）](docs/development/SETUP_JA.md) · [Developer setup (English)](docs/development/SETUP_EN.md) · [アーキテクチャ](docs/architecture/OVERVIEW.md) · [API](docs/api/README.md) · [セキュリティ](SECURITY.md) · [変更・協力について](CONTRIBUTING.md)

## お問い合わせ

[GitHub Issues](https://github.com/k-botsui/lumvia/issues)をご利用ください。Issueやアプリ内の問い合わせから送信する文章は公開されます。個人の動画・認証情報・秘密を含むログは投稿しないでください。

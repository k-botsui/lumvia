# 0002: 外部プラットフォームはREFERENCEとして追加する

採用: 2026-10-09

更新: 公開動画の一時取得については、ユーザーの明示的な選択により[ADR 0005](0005-local-only-contact-and-public-previews.md)を採用しました。以下の動画取得を行わない記述は、リンク登録時と永続保存についての境界として残します。

ユーザーはYouTube・X・Instagram・TikTokで見つけた動画を簡単に追加したい。Source/Media/Assetの境界とREFERENCE/MANAGEDの意味を維持し、サービスへのログインや動画取得の権限を暗黙に要求しない。

## 決定

- 単一の「リンクを貼る」画面と `POST /imports` を使用する。フロントでは最大20件を逐次追加し、成功・重複・失敗を個別表示する。
- Sourceに正規URL・外部ID・取得した最小メタデータを保存し、MediaはREADY/REFERENCEにする。動画の長さ・容量を推定しない。動画AssetとJobは作らない。2026-10-09の改修でカバー画像Assetの保存に対応した。
- アダプターがURL、タイトル取得、サービス、能力を正規化する。コアのShelf・Collection・検索・メモ・お気に入りにサービス固有の条件を追加しない。
- Library/kind/external_idのユニーク制約とLibrary行ロックにより重複を防ぐ。ネットワーク通信中はロックを持たず、取得後に再検査する。重複時にユーザーのメモ・タイトルを変更しない。
- oEmbedは固定HTTPSホストのみ、DNS全アドレス検査とIP固定、TLSホスト名検証、タイムアウト、64 KiB、リダイレクト禁止。TikTok短縮リンクだけHEADで最大3回検証する。動画ページやユーザー指定画像をGETしない。
- InstagramはMetaアプリトークンなしでメタデータ取得しない。各サービスのパスワード・cookieを保存しない。タイトル取得が失敗しても参照は保存する。
- iframeはクリック後に表示し、サービス側のスクリプトを親Originで実行しない。常に元サービスへのリンクを提供する。当初はCell・解析・ダウンロードをMANAGEDに限定した。2026-10-09のユーザー要求により、リンクの時刻付きCellと元動画の追加に対応した（[ADR 0004](0004-unified-shelves-and-trimming.md)）。解析・MP4書き出しはMANAGEDに限定し、APIでも拒否する。
- JSON出力schema_versionを2に上げ、Sourceと正規URL・YouTube開始位置を含める。リンク削除は参照だけを削除する。

カバーは既知のYouTube/TikTok CDNだけをDNS/IP固定・TLS検証付きで取得し、2 MiB・3回までの再検証付きリダイレクトに制限する。JPEGに正規化して私的に保存する。任意のOG画像URLは取得しない。X・Instagramや取得できないリンクは、所有者がカバー写真を選べる。変更したカバーを自動取得で上書きしない。保存が成功した入力URLは消し、失敗分だけ残す。

## 結果と制限

通常のライブラリ機能は外部サービスの稼働・ログインに依存しない。埋め込み再生は投稿の公開設定、削除、地域、認証、サービス側の制限に左右される。保存は元動画の永続保存を意味しない。Instagramの共有リダイレクト・t.coなど任意短縮URLは対応しない。TikTok短縮リンクの確認に失敗した場合は動画ページのURLを案内する。

参考: [YouTube player parameters](https://developers.google.com/youtube/player_parameters)、[YouTube埋め込み](https://support.google.com/youtube/answer/171780?hl=ja)、[X埋め込み](https://help.x.com/en/using-x/how-to-embed-a-post)、[Instagram oEmbed](https://developers.facebook.com/documentation/instagram-platform/oembed)、[TikTok Embed Player](https://developers.tiktok.com/docs/en/embed-player)。X/Instagramのiframe経路は公式widgets.js/embed.jsとHTTPS応答でも確認した。外部サービスの実行可能HTMLを保存・挿入しない。

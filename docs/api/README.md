# API v1

ローカルAPIのOpenAPIは `http://127.0.0.1:8000/api/openapi.json`、対話文書は `/api/docs`。productionでは両方を無効化します。ブラウザーからはNext.js経由で同じOriginの `/api/v1` を使用します。

| リソース | 操作 |
| --- | --- |
| `/auth/options`, `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/password` | 認証・パスワード管理 |
| `/auth/oidc/login`, `/auth/oidc/callback` | 現行設定では無効（404） |
| `/media`, `/media/{id}` | multipart追加、一覧、取得、編集、削除 |
| `/imports` | 4サービスの共有URLをREFERENCEとして追加。`{url, title?, shelf_id?, collection_id?}`。新規201、保存済み200 |
| `/assets/{id}` | 認可された動画・画像配信。`download=true` で元動画を保存 |
| `/media/{id}/cover`, `/media/{id}/reference-cover` | カバーのmultipart PUT、参照カバー取得のPOST |
| `/cells`, `/cells/{id}` | 区間CRUD。所有者のCell単体GETを含む |
| `/cells/{id}/clip` | POST。認証・CSRF付きのMP4書き出し、最大64 MiB |
| `/shelves`, `/collections`, 各 `/{id}/items` | 整理先CRUDと所属変更 |
| `/shelves/{id}/batch`, `/collections/{id}/batch` | PUTで複数の動画・Cellを一括追加 |
| `/shelves/{id}/header`, `/collections/{id}/header` | ヘッダー画像のGET、multipart PUT、DELETE |
| `/media/{id}/analysis`, `/media/{id}/analysis/{run_id}` | 解析要求・結果・解析履歴の削除 |
| `/analysis/capabilities` | 利用可能な解析機能 |
| `/jobs`, `/jobs/{id}/cancel`, `/jobs/{id}/retry` | 進捗・キャンセル・再試行 |
| `/batches`, `/batches/{id}` | 一括追加の集計 |
| `/search` | 動画・Cell・時刻付き検索 |
| `/library/stats`, `/library/export` | 集計・メタデータ出力 |
| `/library/delete-batch` | POSTで複数の動画・Cellを一括削除 |

ログイン後、cookie `lumvia_session` を付けます。書き込みには `lumvia_csrf` cookieの値を `X-CSRF-Token` ヘッダーに付けます。Originがある場合はAPP_URLと一致する必要があります。

追加の `Idempotency-Key` はUUIDで、同じLibrary・同じ内容の再送は同じMediaを返します。同じキーの異なる内容は409です。書き込み一般を自動再試行しません。

`POST /imports` は `{media, created, start_ms, metadata_available}` を返します。同じLibrary・サービス・外部IDのURLは同じMediaを返し、既存のタイトル・メモを上書きしません。所有者が異なれば別の参照です。メタデータ取得失敗時も参照を保存します。ホーム・プロフィール・未対応ホストは422、リンク上限は413、レート超過は429。外部認証情報は受け付けません。

Mediaの `source` はprovider・label・url・external_id・author・start_ms・thumbnail_url・capabilitiesを返します。REFERENCEには動画Assetがなく、長さ・容量は未知のため0です。カバー用thumbnail Assetは保存できます。REFERENCEにも時刻付きCellを保存でき、解析・MP4書き出し要求は409 `REFERENCE_UNSUPPORTED`。`/library/export` のschema_version 2はsourceと整理先の識別子を追加します。

一覧の `offset` は0以上、`limit` は1〜100（既定値はリソースによる）。検索は各種類に同じoffset/limitを適用し、種類ごとのcountsを返します。Cell境界は `start_ms` / `end_ms` の整数で、MANAGEDは `0 <= start < end <= media.duration_ms`、REFERENCEは `0 <= start < end <= 3600000` を要求します。

Cellは5分以内・動画ごと100件・Library全体2,000件。同じMedia・開始・終了の再作成は既存Cellを返し、タイトル等を上書きしません。`POST /cells/{id}/clip` はプレビューから正確な区間をH.264/AAC MP4へ書き出し、`Content-Disposition: attachment` を返します。同時1件・120秒・64 MiB・8回/時の上限。永続Assetは追加しません。REFERENCEは元動画追加後に利用できます。


動画数500本・シーン検出履歴10回/動画が既定の上限です。`/library/stats` のlimitsには設定値が含まれます。件数上限は413、同時処理またはレート制限は429。カバーPUTは静止JPEG・PNG・WebPをJPEGに正規化し、設定したカバーを自動取得から保護します。

エラーは `{ "error": { "code": "...", "message": "..." }, "request_id": "..." }`。HTTPヘッダー `X-Request-ID` でログ・監査・Jobに関連付けられます。セッション、所有権、内部パスは返しません。v1に破壊的変更を加える場合は新バージョンと移行期間を設けます。

新規Cellは元動画のShelf/互換Collection所属を引き継ぎ、あとから独立して所属を変更できます。Shelfのitemsはmedia_idまたはcell_idの一方を受け付けます。`GET /cells?shelf_id=...` で所属Cellを取得し、Cellのshelf_idsとgroupのcell_count、JSON出力shelf_cellsに所属を含めます。画面の整理先はShelfへ統一し、既存collections APIは互換性のため維持します。

一括追加PUTの本文は `{ "media_ids": ["id"], "cell_ids": ["id"] }`。重複を除いて合計1〜100件です。整理先とすべての項目の所有権を先に検証し、1件でも存在しない・他所有者の項目なら404を返して全件を追加しません。所属は同じトランザクションで追加し、登録済みの所属は複製せず、成功時は204を返します。空の選択または上限超過は422です。

`POST /library/delete-batch` も同じ本文と件数上限を使います。全項目の所有権を検証し、動画と指定Cellをロックしてから1トランザクションで削除します。存在しない・他所有者の項目は404、動画に待機・実行中Jobがある場合は409で、全件を削除しません。動画に付随するCell・所属は削除され、Cellだけの指定では元動画を残します。成功は204、関連Assetは既存の削除キューで回収します。

ヘッダーPUTはmultipart `file` に静止JPEG・PNG・WebP、50 MiB以下・縦横12,000px以下・6,000万画素以下を要求します。最大1600×900pxへ縮小し、メタデータを除いたJPEGとして私的ストレージへ保存します。1アカウント30回/時、画像復号は既存の同時2件上限です。返却groupと一覧の `header_url` は所有権を要求する画像GETを指し、ローカル配信は `Cache-Control: no-store` を返します。未設定はnull、画像GETは404です。置換・画像DELETE・Shelf削除は古い画像を削除キューに追加します。名前・説明・色のPATCHはヘッダーを維持します。

動画追加multipartは任意のshelf_id/collection_id（一方のみ）を受け付けます。所有権を検証し、所属を同一トランザクションで保存します。`reference_id` を指定すると所有者のREFERENCEへファイルを追加し、同じMediaをMANAGEDにします。Cell・メモ・タイトル・Source URL・所属・カスタムカバーは保持し、保存済みCellより短い動画は422 `CELL_OUTSIDE_VIDEO`、追加済みは409 `ALREADY_MANAGED`。同一Idempotency-Keyの再送は重複取り込みしません。

`PATCH /shelves/{id}/header` と既存 `/collections/{id}/header` は `{ "x": 50, "y": 50, "zoom": 1 }` を受け、groupの `header_frame` を更新します。x/yは有限値0〜100、zoomは1〜3、余剰フィールドは拒否。所有者認可とCSRF必須、画像がなければ409。保存画像は変更せず、画像置換・取り外し時は中央に戻します。

`POST /media/{id}/reference-preview` は所有するREFERENCEの公開動画だけを一時取得します。CSRF・8回/時・同時1件、10分・32 MiB・90秒まで。戻り値は `{ "url": "/api/v1/media/{id}/reference-preview", "duration_ms": 24133, "width": 360, "height": 640, "expires_at": 0 }`（expires_atは実際のUnix秒）。動画GETは認可付きRange配信、info GETは `/media/{id}/reference-preview/info`。30分で失効し404、取得不能422、使用中429。永続Media/Asset・動画の合計時間・保存容量を変更しません。

`GET /support` は認証必須で `{ "github_url": null, "local_only": true }` を返します。管理者の `SUPPORT_GITHUB_REPOSITORY=owner/repository` 設定時だけ `https://github.com/owner/repository/issues/new` を返します。問い合わせ送信・添付・本文保存のAPIはありません。

シーン検出は `{ "analyzer": "scenes" }` だけを受け付けます。人物登録APIは削除し、旧モデルの解析要求は422、再試行は409で拒否します。過去の解析・文字起こしは検索結果に表示せず、保存済みCellと由来のDB記録は維持します。

| 問い合わせAPI | 用途 |
| --- | --- |
| `GET /support` | 投稿先・共通窓口の接続状態 |
| `POST /support` | 件名・本文をIssueへ送信。request_idも必須。成功201、未接続503、重複中409、結果不明502 |

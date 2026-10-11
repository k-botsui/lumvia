# バックアップと復元

メタデータJSONには動画本体や認証情報はありません。完全な保存にはDBとstorageの両方が必要です。

このスクリプトは`/opt/homebrew/opt/postgresql@17/bin`とネイティブDBの55432番/`lumvia`を使用します。現行の自動化はApple Silicon Mac向けで、Linux・Windows・Docker volumeのバックアップとしては未対応です。Macネイティブで処理が完了した状態で次を実行します。

```sh
.venv/bin/python scripts/backup.py
```

アプリを一時停止し、PostgreSQLのカスタム形式dump、storageのtar.gz、件数とSHA256のmanifestを `~/Library/Application Support/Lumvia/backups/UTC日時/` に保存します。新しく作った検証DBへ実際にrestoreして主要テーブルの件数を照合し、その検証DBだけを削除します。前にアプリが動いていた場合は最後に再起動します。進行中のJobがあるとバックアップを中止します。

バックアップは権限600/700、ソースコードの外に置きます。動画、メモ、パスワードハッシュ、監査情報、登録した人物の顔画像・特徴量を含むため、私的な暗号化保存先へ保管してください。`config.env` と初期パスワードは含めません。別の安全な方法で保管してください。Docker volumeはこのスクリプトの対象外です。一時公開動画のキャッシュは含めません。

人物探索は現行機能から撤去しましたが、旧データがある場合はbackupにも含まれます。manifestの`secrets_included: false`は設定と初期平文passwordを同梱しないという意味で、DB内のpassword hash・Session・監査や個人情報が除外される意味ではありません。バックアップ自体への暗号化や世代削除は自動化していません。

## 手動の復元手順

1. 空の別環境を作り、現環境の動画を上書きしないようにします。
2. `manifest.json` のチェックサムを確認し、信頼できる自分のバックアップだけを使います。
3. アプリを止めて、新しいPostgreSQL DBに `pg_restore --no-owner --exit-on-error` で `database.dump` を取り込みます。接続秘密情報は環境変数または600権限のpgpassで渡します。
4. `storage.tar.gz` の `storage/` を新環境の私的保存先へ復元します。tarの絶対パス・シンボリックリンクを拒否できる抽出設定を使用します。
5. 私的データ基点の `config.env` のDB・storage設定を新環境に合わせ、Alembicをheadへ進めます。旧環境を保管したまま、動画再生・Cell検索・元動画ダウンロードを確認します。
6. 実運用へ戻す前に、不要な旧セッションを失効させてください。新しい管理者パスワードを設定したら、古い初期ログイン情報を再使用しません。

上書き復元を自動化していません。まず別環境への復元結果を確認してから切り替えてください。

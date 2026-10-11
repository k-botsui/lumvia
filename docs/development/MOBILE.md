# 自分のスマホから使う

パスワード認証は通常構成・HTTPS構成の両方で使用します。productionではHTTPSとSecure cookieを必須にし、CSRF・Origin・所有者認可を維持します。外部アカウントログインは使用しません。

この構成は、**自分のPCに保存し、同じ私的Wi-FiのiPhone・Androidから使う**ための任意設定です。通常起動には含まれません。スマホ単体での保存・バックエンド実行・オフライン利用には対応していません。PCは起動したままにします。

画面のタッチ操作と320〜768pxのレイアウトはブラウザーで確認しています。Docker実起動、iPhone・Androidの証明書導入と実接続は、この環境では未検証です。

## 準備

1. [Docker版](DOCKER.md)を準備します。ネイティブ版とは別の保存先・アカウントです。
2. PCと自分のスマホを同じWi-Fiへ接続します。PCのWi-Fi IPv4アドレスをOSのネットワーク設定で確認します。以下は `192.168.1.10` の例です。実際の値に置き換えます。
3. プロジェクト直下で設定だけを準備します。このコマンドでは待ち受けを開始しません。

```sh
python3 scripts/configure_mobile.py 192.168.1.10
```

Windowsでは `python3` を `py -3` に置き換えます。秘密情報は既存の値を維持します。許可するIPは10/8、172.16/12、192.168/16だけです。

## HTTPSを起動する

```sh
python3 scripts/run_compose.py start --mobile
```

ゲートウェイは指定した私的IPの8443番にだけ追加します。PC・スマホとも `https://192.168.1.10:8443` を使います。スマホから `127.0.0.1` を開いてもPCには接続できません。通常のHTTP画面はスマホ用のSecure cookieを利用できません。

Caddyがこのインストール専用のローカルCAを作り、通信を暗号化します。公的認証局、トンネル、クラウド、公開DNSは使いません。OSのファイアウォール設定が必要な場合は、私的ネットワークの8443番だけを対象にします。ルーターのポート転送は設定しません。

## 自分の端末で証明書を信頼する

ブラウザーの証明書警告を回避して使う構成にはしません。PC上で公開ルート証明書だけを取り出します。プロジェクト直下で、保存先の `<private-compose-env>` をOSごとの `compose.env` の絶対パスに置き換えます。

```sh
docker compose --env-file "<private-compose-env>" -f compose.yaml -f infrastructure/docker/mobile.compose.yaml cp mobile:/data/caddy/pki/authorities/local/root.crt "<private-output>/lumvia-root.crt"
```

`root.crt` は公開証明書です。`root.key` やDockerのCA volume・秘密情報をコピーしてはいけません。証明書は自分の端末へ直接渡し、OSの証明書設定から手動で信頼します。PC側にも同じ証明書を設定します。信頼の設定は利用者自身が行い、アプリは自動変更しません。

- iPhone・iPad: [Appleの証明書信頼手順](https://support.apple.com/en-us/102390)。手動で導入した証明書はSSL用に自動で信頼されないため、設定の「一般」→「情報」→「証明書信頼設定」で、このPCのCAを確認します。
- Android: [Googleの証明書導入手順](https://support.google.com/pixelphone/answer/2844832)。項目名はメーカーとOSにより異なります。自分で取り出したCA証明書を指定します。

信頼設定が済み、HTTPSの警告がないことを確認してからDocker版の `Dockerログイン情報.txt` でログインします。HTTPS構成の認証はAPIテストで検証し、実端末接続の検証範囲は検証記録を参照してください。端末の共有やパスワードの共有は前提にしません。Wi-FiのIPが変わったら停止して準備コマンドを実行し直します。

## 停止・PCだけの利用へ戻す

```sh
python3 scripts/run_compose.py stop --mobile
python3 scripts/run_compose.py start
```

通常起動は追加ゲートウェイを停止し、ループバックだけに戻します。DB・動画のvolumeは残します。証明書の信頼設定はOSの管理なので、不要になった場合は自分の端末から取り外します。

ブラウザーの「ホーム画面に追加」は画面への入口を作るだけです。インストールしたネイティブアプリやオフライン保存にはなりません。外部リンクのメタデータ・プレーヤー・一時取得には、従来どおり配信元への通信が発生します。

実装の根拠: [Caddy local HTTPS](https://caddyserver.com/docs/automatic-https#local-https)、[内部TLS](https://caddyserver.com/docs/caddyfile/directives/tls)、[Composeの構成マージ](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)。

# Windows・macOS・LinuxのDocker版

Windowsの起動スクリプトとOSごとの私的設定パスを用意しています。Compose v5.6.0で通常構成・スマホ用構成の設定解決を確認しました。監査環境にはDockerデーモンがないため、イメージのビルド・コンテナー実起動、Windows実機の確認は未実施です。現在動作確認した構成はmacOSネイティブ起動です。

## Windows 11

1. Python 3.13と[Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)を導入します。DockerのWSL 2等の要件は公式手順で確認してください。
2. Docker Desktopを起動し、Linuxコンテナーを使用します。
3. プロジェクトの `Lumvia-start.cmd` を開きます。初回はイメージをビルドするため時間がかかります。
4. `Lumvia-login.cmd` で初期アカウントを確認します。ブラウザーは `http://127.0.0.1:3000` です。
5. 停止は `Lumvia-stop.cmd`。DBと動画は残ります。

cmdと同等の実行:

```powershell
py -3 scripts/run_compose.py start
py -3 scripts/run_compose.py login
py -3 scripts/run_compose.py status
py -3 scripts/run_compose.py stop
```

## macOS・Linux

Docker/Compose v2.20以上とPython 3.13を準備し、プロジェクト直下で実行します。ネイティブ版を起動している場合は先に停止し、3000番を空けます。

```sh
python3 scripts/run_compose.py start
python3 scripts/run_compose.py login
python3 scripts/run_compose.py status
python3 scripts/run_compose.py stop
```

## 保存先と起動の境界

| OS      | 設定とログイン情報                                       |
| ------- | -------------------------------------------------------- |
| Windows | `%LOCALAPPDATA%\Lumvia\`                                 |
| macOS   | `~/Library/Application Support/Lumvia/`                  |
| Linux   | `$XDG_DATA_HOME/lumvia/` または `~/.local/share/lumvia/` |

設定は `compose.env`、ログイン情報は `Dockerログイン情報.txt`。初回だけ秘密情報を生成し、再起動で置き換えません。スクリプトは引数配列を使い、空白や日本語を含むパスを扱います。Windowsのアクセス制御はOSのユーザープロファイルの権限に従います。

DB・動画・一時プレビューは自分のPC内のDocker volumeに置きます。ネイティブ版とDocker版はDB・アカウントが別です。ネイティブの `config.env` とデータは変更しません。

initializeでmigrationと最初のアカウント作成を行います。API/workerは非root・読み取り専用、動画は専用volume、作業領域は制限付きtmpfsです。DB・RabbitMQ・Redis・APIにホストの公開ポートはありません。通常版のWebはループバックだけです。API/workerにはリンク情報と公開動画を取得するための外向き通信を許可し、DB/キューは内部ネットワークに置きます。

通常停止はvolumeを残します。`down -v` はDBと動画を消すため使用しません。任意の[スマホ接続](MOBILE.md)は `--mobile` で明示したときだけ追加します。通常起動・停止の `--remove-orphans` は追加ゲートウェイを回収します。

スマホ用production構成でもローカルパスワードで認証します。HTTPS、Secure cookie、CSRF、Origin、所有者認可を維持します。実端末の証明書導入と接続は検証記録の対象範囲を確認してください。

コンテナー版を配布する前には、実起動・イメージ監査とdigest固定・バックアップ復元を別環境で確認します。この構成をインターネット公開には使いません。

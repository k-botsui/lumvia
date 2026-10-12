# 第三者のライブラリと素材

Lumviaのオリジナル部分には個人の私的・非商用利用を許可するLICENSEを適用します。依存ライブラリの許諾は各ライブラリのライセンスに従い、ルートのLICENSEによって変更しません。依存はパッケージマネージャーから取得し、node_modules、Python環境、モデル、実行バイナリはソースのGit管理対象には同梱しません。Macアプリの配布物では、以下に従って実行に必要な依存を同梱します。

主要な依存はNext.js/React/TypeScript/Three.js/FastAPI/SQLAlchemy/Alembic/Celeryなどです。バージョンは `apps/web/pnpm-lock.yaml` と `apps/api/requirements.txt` に記録します。全推移依存の名称・バージョン・ライセンスは `docs/development/DEPENDENCY_LICENSES.json` を参照してください。

FFmpeg、PostgreSQL、RabbitMQ、Redis、Docker、Caddyは利用者が別途導入するツールです。コンテナーイメージやバイナリを再配布する場合は、それぞれの配布物とビルドオプションに対する許諾・ソース提供義務等を別途確認してください。

`apps/web/public/sample.mp4` は本プロジェクト用に作成した色面と線によるサンプルです。アプリのアイコン・ロゴ・Three.jsの構図はプロジェクトのブランド素材で、ルートLICENSEの対象です。商標・ロゴの使用許諾は付与しません。

宣伝映像の制作フォルダー `marketing/`、参考ブランド画像、作業スクリーンショット、個別引き継ぎ記録は公開対象から除外しています。Pexels、Mixkit、Incompetech、SoundFont等の未編集原素材・音源単体・制作中間ファイルは同梱しません。完成した宣伝映像は `demo/` に含み、その第三者素材は各素材のライセンスに従います。宣伝映像を別途公開する際は、素材単位のライセンスと帰属表示を確認してください。

外部動画へのリンクやプレーヤー対応は、その動画の著作権・利用権の許諾を与えるものではありません。利用権のある素材で動作を確認してください。

完成したDemoの素材クレジットは[demo/README.md](demo/README.md)を参照してください。

## Macアプリの配布物

Mac版の依存はNode.js（MIT等）、Pythonとその依存（PSF等、各配布物の表示に従う）、PostgreSQL（PostgreSQL License）、Valkey（BSD等）、FFmpeg（LGPL 2.1以降、GPL・nonfreeを無効にした共有ライブラリ構成）です。アプリ内のThirdPartyおよび各パッケージのライセンス表示を保持します。FFmpeg等の対応ソースZIPをアプリと一緒に配布します。Mac版にはRabbitMQ、Erlang、Redisサーバーを含めません。

Lumviaの改変・再配布の制限は、第三者のライブラリにそのライセンスが認める改変・交換・再配布・デバッグ等の権利には適用しません。LGPL対象ライブラリの交換・再リンク、その変更をデバッグするためのリバースエンジニアリングなど、LGPLが認める行為を制限しません。第三者ソースZIPのLumvia以外の部分にはそれぞれのライセンスが適用されます。

# 第三者のライブラリと素材

Lumviaのソースは閲覧目的で公開します。依存ライブラリの許諾は各ライブラリのライセンスに従い、ルートのLICENSEによって変更しません。依存はパッケージマネージャーから取得し、node_modules、Python環境、モデル、実行バイナリはリポジトリへ同梱しません。

主要な依存はNext.js/React/TypeScript/Three.js/FastAPI/SQLAlchemy/Alembic/Celeryなどです。バージョンは `apps/web/pnpm-lock.yaml` と `apps/api/requirements.txt` に記録します。全推移依存の名称・バージョン・ライセンスは `docs/development/DEPENDENCY_LICENSES.json` を参照してください。

FFmpeg、PostgreSQL、RabbitMQ、Redis、Docker、Caddyは利用者が別途導入するツールです。コンテナーイメージやバイナリを再配布する場合は、それぞれの配布物とビルドオプションに対する許諾・ソース提供義務等を別途確認してください。

`apps/web/public/sample.mp4` は本プロジェクト用に作成した色面と線によるサンプルです。アプリのアイコン・ロゴ・Three.jsの構図はプロジェクトのブランド素材で、ルートLICENSEの対象です。商標・ロゴの使用許諾は付与しません。

宣伝映像の制作フォルダー `marketing/`、参考ブランド画像、作業スクリーンショット、個別引き継ぎ記録は公開対象から除外しています。Pexels、Mixkit、Incompetech、SoundFont、外部参照動画やその制作コピーをこの公開ソースに同梱しません。宣伝映像を別途公開する際は、素材単位のライセンスと帰属表示を確認してください。

外部動画へのリンクやプレーヤー対応は、その動画の著作権・利用権の許諾を与えるものではありません。利用権のある素材で動作を確認してください。

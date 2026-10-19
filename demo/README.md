# Lumvia Demo

28秒・1680フレーム・60fpsのトレーラーV7.1です。V7でホームからライブラリへ自動的に変形していた演出を削除しました。動画がホーム中央のカードへ収まった後もホームを表示し、次の実写カットへ切り替えます。後半の再生・編集・Cell画面も、ホームを開いた背景に揃えました。アプリに存在しない画面移動を表現しません。

V6.1の構成、尺、音楽、実写場面、立体ロゴを保ち、GUIが映る区間（0.8–6秒、12.6–21秒）だけを最新版に更新しています。実装済み画面の撮影画像に再生映像とカメラ移動を合成しています。新しい広告コピーは追加していません。

`lumvia-trailer-v7-1-preview.mp4` は960×540、60fps、H.264/AACのプレビューです。フルHD版は[TEST 7の添付動画V7.1](https://github.com/k-botsui/lumvia/releases/download/v0.2.0-mac-test.7/Lumvia-Trailer-V7.1.mp4)です。音声の圧縮済みパケットはV6.1と同一です。風景映像はV6.1の修正済みフレームを引き継いでいます。

実アプリではホームから開いた動画を閉じる、Escapeで閉じる、ブラウザーで戻る、ホームから開いたCellを閉じる操作でホームを維持することを確認しました。動画の選択も維持します。今回の修正対象はトレーラーと公開資料です。TEST 7のアプリ本体、起動・停止方法、保存先は変更していません。動画の検証結果は[validation-v7-1.json](validation-v7-1.json)に記録しています。

## 素材クレジット

映像は[Pexels License](https://www.pexels.com/license/)に基づいて編集・組込みを行っています。登場する人物・作者がLumviaを推奨していることを示すものではありません。素材の元音声は使用していません。

- カフェ: [Anastasia Shuraeva](https://www.pexels.com/video/people-laughing-together-8943776/)
- 海辺の友人: [RDNE Stock project](https://www.pexels.com/video/friends-laughing-while-walking-on-the-beach-8760574/)
- 車内の友人: [KoolShooters](https://www.pexels.com/video/friends-inside-the-van-8974399/)
- コーヒー: [Taryn Elliott](https://www.pexels.com/video/a-person-pouring-coffee-into-a-cup-on-a-table-4374506/)
- 湖: [Kindel Media](https://www.pexels.com/video/time-lapse-of-a-body-of-water-in-a-picturesque-environment-9010748/)

- 海岸: [Maurice Supple](https://www.pexels.com/video/scenic-coastal-road-with-cliffs-and-blue-ocean-31176451/)

音楽: **Just Keep Walking — Michael Ramir C.** / [Mixkit公式カタログ](https://mixkit.co/free-stock-music/indie-pop/) / [Mixkit Music Free License](https://mixkit.co/license/#musicFree)。完成映像内の利用であり、音源単体は配布しません。

アプリ画面は専用のデモライブラリを用いた制作画面、ロゴはLumviaのブランド素材です。Lumviaの制作部分はルートLICENSEの対象です。第三者素材の権利は各作者に留保され、それぞれの許諾はルートLICENSEによって変更されません。

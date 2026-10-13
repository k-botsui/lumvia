// Link data lives in the URL fragment; it is never sent to this worker.
export const page = `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lumviaリンク集</title><link rel="stylesheet" href="/link-list.css"><script src="/link-list.js" defer></script></head><body><main><h1>Lumviaリンク集</h1><p>受け取ったリンク集を保存し、自分のLumviaで読み込めます。動画本体は含まれません。カバー画像が含まれる場合は、Lumviaで読み込む前に確認できます。</p><p id="status" role="status">共有データを確認しています…</p><ul id="links"></ul><button id="download" disabled>リンク集ファイルを保存</button><p>保存した lumvia-links.txt を、Lumviaの「リンク集を読み込む」で選んでください。</p><p>このページは共有データをサーバーへ保存・送信しません。共有URLを知っている人は内容を閲覧できます。受信先のLumviaで、内容を確認してから追加してください。</p><a href="https://github.com/k-botsui/lumvia" rel="noopener noreferrer">Lumviaについて</a></main></body></html>`;
export const style = `body{font-family:system-ui,sans-serif;background:#f5f7fb;color:#172238;margin:0;padding:24px}main{max-width:680px;margin:32px auto;background:white;padding:28px;border-radius:16px}p,li{line-height:1.8}li{overflow-wrap:anywhere;margin-bottom:16px}span{display:block;font-size:14px;color:#58657b}button{background:#2474ec;color:white;padding:14px 20px;border:0;border-radius:10px;font-size:16px;cursor:pointer}button:disabled{opacity:.5;cursor:default}a{color:#2474ec}`;
export const script = `"use strict";
(async () => {
  const status = document.getElementById("status"), button = document.getElementById("download");
  try {
    const fragment = location.hash.slice(1);
    if (!fragment.startsWith("v1=") || fragment.length > 2000) throw new Error();
    const value = fragment.slice(3);
    if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new Error();
    const bytes = Uint8Array.from(atob(value.replace(/-/g,"+").replace(/_/g,"/")), c => c.charCodeAt(0));
    const reader = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip")).getReader();
    const chunks = []; let length = 0;
    while (true) { const {done, value} = await reader.read(); if (done) break; length += value.length; if (length > 2097152) { await reader.cancel(); throw new Error(); } chunks.push(value); }
    const result = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { result.set(chunk,offset); offset += chunk.length; }
    const bundle = JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(result));
    if (bundle.format !== "lumvia-link-list" || ![1, 2].includes(bundle.version) || !Array.isArray(bundle.links) || !bundle.links.length || bundle.links.length > 2000 || !Array.isArray(bundle.cells) || !Array.isArray(bundle.groups)) throw new Error();
    const list = document.getElementById("links");
    for (const link of bundle.links) { if (typeof link.title !== "string" || link.title.length > 200 || typeof link.url !== "string" || link.url.length > 2048) throw new Error(); const item = document.createElement("li"), title = document.createElement("strong"), url = document.createElement("span"); title.textContent = link.title; url.textContent = link.url; item.append(title,url); list.append(item); }
    status.textContent = "リンク " + bundle.links.length + "件・Cell " + bundle.cells.length + "件・Shelf " + bundle.groups.length + "件。メモ等を含む場合は、Lumviaの読み込み確認画面で表示されます。";
    button.disabled = false;
    button.addEventListener("click", () => { const file = URL.createObjectURL(new Blob([JSON.stringify(bundle)],{type:"text/plain;charset=utf-8"})); const a = document.createElement("a"); a.href = file; a.download = "lumvia-links.txt"; a.click(); setTimeout(() => URL.revokeObjectURL(file),1000); });
  } catch { document.getElementById("links").replaceChildren(); status.textContent = "共有URLが壊れているか、このブラウザーでは読み込めません。送り主にリンク集ファイルを送ってもらってください。"; }
})();`;

export function linkPage(path) {
  const assets = {
    "/link-list": [page, "text/html; charset=utf-8"],
    "/link-list.js": [script, "text/javascript; charset=utf-8"],
    "/link-list.css": [style, "text/css; charset=utf-8"],
  };
  const asset = assets[path];
  if (!asset) return null;
  return new Response(asset[0], {
    headers: {
      "Content-Type": asset[1],
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "X-Frame-Options": "DENY",
      "Content-Security-Policy":
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    },
  });
}

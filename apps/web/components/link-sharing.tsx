'use client';

import { useRef, useState } from 'react';
import { Download, Upload, Copy, Share2, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Modal } from './ui/dialog';

type Scope = {
  kind: 'library' | 'shelves' | 'collections';
  group_id?: string;
  media_ids?: string[];
  cell_ids?: string[];
};
type Bundle = {
  format: 'lumvia-link-list';
  version: 1 | 2;
  links: {
    key: string;
    url: string;
    title: string;
    tags: string[];
    note: string;
    favorite: boolean;
    cover_jpeg?: string;
  }[];
  cells: {
    key: string;
    link: string;
    title: string;
    start_ms: number;
    end_ms: number;
    tags: string[];
    note: string;
  }[];
  groups: {
    key: string;
    name: string;
    description: string;
    header_jpeg?: string;
    links: string[];
    cells: string[];
  }[];
};
type Summary = { new_links: number; existing_links: number; new_cells: number; groups: number };
type ExportPreview = {
  bundle: Bundle;
  excluded: { title: string; reason: string }[];
  excluded_cells: number;
  notes_included: boolean;
};
type ImportPreview = { bundle: Bundle; summary: Summary; duplicate: boolean };
const maximum = 2 * 1024 * 1024;

export function LinkSharing({
  scope,
  label = 'リンク集を共有',
  onChanged,
  notify,
}: {
  scope: Scope;
  label?: string;
  onChanged: () => void;
  notify: (message: string) => void;
}) {
  const [mode, setMode] = useState<'export' | 'import' | null>(null);
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [incoming, setIncoming] = useState<ImportPreview | null>(null);
  const [text, setText] = useState('');
  const [notes, setNotes] = useState(false);
  const [images, setImages] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState('');
  const pending = useRef(false);
  const generation = useRef(0);

  function close() {
    generation.current++;
    setMode(null);
  }
  async function prepare(includeNotes = false, includeImages = false) {
    const current = ++generation.current;
    setMode('export');
    setPreview(null);
    setIncoming(null);
    setError('');
    setResult('');
    setNotes(includeNotes);
    setImages(includeImages);
    setAgreed(false);
    setBusy(true);
    try {
      const data = await api<ExportPreview>('/link-shares/export-preview', {
        method: 'POST',
        body: JSON.stringify({ ...scope, include_notes: includeNotes, include_images: includeImages }),
      });
      if (generation.current === current) setPreview(data);
    } catch (failure) {
      if (generation.current === current)
        setError(failure instanceof Error ? failure.message : '共有内容を確認できませんでした。');
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  function beginImport() {
    generation.current++;
    setMode('import');
    setIncoming(null);
    setPreview(null);
    setText('');
    setError('');
    setResult('');
    setAgreed(false);
    setBusy(false);
  }
  async function inspect(value: string) {
    const current = ++generation.current;
    setBusy(true);
    setIncoming(null);
    setError('');
    setAgreed(false);
    setResult('');
    try {
      if (new TextEncoder().encode(value).length > maximum) throw new Error('共有ファイルは2 MBまでです。');
      let bundle: unknown;
      try {
        bundle = JSON.parse(value.replace(/^\uFEFF/, ''));
      } catch {
        throw new Error('Lumviaリンク集のファイルまたは共有データを選んでください。');
      }
      const data = await api<ImportPreview>('/link-shares/import-preview', {
        method: 'POST',
        body: JSON.stringify(bundle),
      });
      if (generation.current === current) setIncoming(data);
    } catch (failure) {
      if (generation.current === current)
        setError(failure instanceof Error ? failure.message : '読み込めませんでした。');
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  function file() {
    return new File([JSON.stringify(preview!.bundle)], 'lumvia-links.txt', {
      type: 'text/plain;charset=utf-8',
    });
  }
  function download() {
    if (!agreed || !preview?.bundle.links.length) return;
    const url = URL.createObjectURL(file());
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'lumvia-links.txt';
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setResult('共有ファイルを保存しました。受け取った人はLumviaの「リンク集を読み込む」で追加できます。');
  }
  async function copy() {
    if (!agreed || !preview?.bundle.links.length) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(preview.bundle));
      setResult('共有データをコピーしました。全文を受け取った人は「リンク集を読み込む」に貼り付けられます。');
    } catch {
      setError('コピーできませんでした。「ファイルを保存」を使ってください。');
    }
  }
  async function copyShareUrl() {
    if (!agreed || !preview?.bundle.links.length) return;
    setError('');
    try {
      if (typeof CompressionStream === 'undefined')
        throw new Error('このブラウザーではSNS用URLを作れません。ファイルを保存してください。');
      const stream = new Blob([JSON.stringify(preview.bundle)])
        .stream()
        .pipeThrough(new CompressionStream('gzip'));
      const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
      const code = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(''))
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '');
      const url = 'https://lumvia-support.lumvia-support-worker.workers.dev/link-list#v1=' + code;
      if (url.length > 2000)
        throw new Error(
          'このリンク集はSNS用URLには大きすぎます。メモを除くか項目を減らす、またはファイルで共有してください。',
        );
      await navigator.clipboard.writeText(url);
      setResult(
        'SNS用URLをコピーしました。受け取った人はURLを開いてリンク集ファイルを保存できます。URLを知っている人は内容を閲覧できます。',
      );
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'SNS用URLを作れませんでした。ファイルで共有してください。',
      );
    }
  }
  async function apply() {
    if (!incoming || !agreed || incoming.duplicate || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      const response = await api<{ duplicate: boolean; summary: Summary }>('/link-shares/import', {
        method: 'POST',
        body: JSON.stringify({ bundle: incoming.bundle, confirmed: true }),
      });
      const message = response.duplicate
        ? 'このリンク集は読み込み済みです。二重登録していません。'
        : `リンク${response.summary.new_links}件・Cell${response.summary.new_cells}件を追加しました。既存リンク${response.summary.existing_links}件は再利用しました。`;
      setIncoming({ ...incoming, duplicate: true });
      setResult(message);
      notify(message);
      onChanged();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '読み込めませんでした。');
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  const bundle = mode === 'export' ? preview?.bundle : incoming?.bundle;
  return (
    <>
      <button className="button secondary" onClick={() => prepare()}>
        <Share2 size={16} />
        {label}
      </button>
      <button className="button secondary" onClick={beginImport}>
        <Upload size={16} />
        リンク集を読み込む
      </button>
      <Modal
        open={mode !== null}
        onClose={close}
        title={mode === 'export' ? 'リンク集を共有' : 'リンク集を読み込む'}
        wide
        className="link-share-modal"
      >
        <div className="link-sharing">
          {mode === 'export' ? (
            <>
              <p>
                外部リンクと、そのCell・Shelf構成を共有します。動画本体・アカウント情報・ログ・保存場所は含めません。画像は下の項目で追加できます。
              </p>
              <label className="share-check">
                <input
                  type="checkbox"
                  checked={notes}
                  disabled={busy}
                  onChange={(e) => prepare(e.target.checked, images)}
                />
                メモとShelfの説明も含める（個人情報に注意）
              </label>
              <label className="share-check">
                <input
                  type="checkbox"
                  checked={images}
                  disabled={busy}
                  onChange={(event) => prepare(notes, event.target.checked)}
                />
                カバー画像とShelfヘッダーも含める（共有する権利・個人情報を確認）
              </label>
            </>
          ) : (
            !incoming && (
              <>
                <p>
                  受け取った「lumvia-links.txt」を選ぶか、共有データを貼り付けてください。確認するまでライブラリには追加しません。
                </p>
                <label className="button secondary">
                  ファイルを選ぶ
                  <input
                    className="sr-only"
                    type="file"
                    accept=".txt,.json,text/plain,application/json"
                    disabled={busy}
                    onChange={async (e) => {
                      const selected = e.target.files?.[0];
                      e.target.value = '';
                      if (!selected) return;
                      if (selected.size > maximum) {
                        setError('共有ファイルは2 MBまでです。');
                        return;
                      }
                      try {
                        await inspect(await selected.text());
                      } catch {
                        setError('ファイルを読み取れませんでした。');
                      }
                    }}
                  />
                </label>
                <label htmlFor="share-data">共有データを貼り付け</label>
                <textarea
                  id="share-data"
                  rows={4}
                  maxLength={maximum}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="受け取った共有データの全文"
                  disabled={busy}
                />
                <button
                  className="button secondary"
                  onClick={() => inspect(text)}
                  disabled={busy || !text.trim()}
                >
                  内容を確認
                </button>
              </>
            )
          )}
          {busy && (
            <p role="status">
              <Loader2 size={16} className="spin" />
              確認しています…
            </p>
          )}
          {bundle && (
            <>
              <h3>
                リンク {bundle.links.length}件・Cell {bundle.cells.length}件・Shelf {bundle.groups.length}件
              </h3>
              {mode === 'export' && preview && (
                <>
                  <p>
                    共有しない項目：{preview.excluded.length}件、対象外のCell {preview.excluded_cells}
                    件。
                    {images
                      ? '保存済みのカバーとShelfヘッダーを小さなJPEGとして含めます。既存の画像は上書きしません。'
                      : 'カバー画像とShelfのヘッダー画像も除外します。'}
                  </p>
                  {!!preview.excluded.length && (
                    <details>
                      <summary>除外する項目を見る</summary>
                      <ul>
                        {preview.excluded.map((entry, i) => (
                          <li key={i}>
                            {entry.title} — {entry.reason}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </>
              )}
              {mode === 'import' && incoming && (
                <p>
                  {incoming.duplicate
                    ? 'このリンク集は読み込み済みです。二重登録しません。'
                    : `新しいリンク ${incoming.summary.new_links}件、既存リンク ${incoming.summary.existing_links}件を再利用します。既存のタイトル・メモ・タグは上書きしません。`}
                </p>
              )}
              <div className="share-preview">
                <ul>
                  {bundle.links.map((entry) => (
                    <li key={entry.key}>
                      {entry.cover_jpeg && (
                        <img
                          src={`data:image/jpeg;base64,${entry.cover_jpeg}`}
                          alt={`${entry.title}の共有カバー`}
                          style={{ maxWidth: 160, maxHeight: 100 }}
                        />
                      )}
                      <strong>{entry.title}</strong>
                      <span>{entry.url}</span>
                      {entry.favorite && <span>お気に入り</span>}
                      {!!entry.tags.length && <span>{entry.tags.join('・')}</span>}
                      {entry.note && <p>{entry.note}</p>}
                    </li>
                  ))}
                </ul>
                {!!bundle.cells.length && (
                  <details>
                    <summary>Cellの区間・メモを見る</summary>
                    <ul>
                      {bundle.cells.map((entry) => (
                        <li key={entry.key}>
                          {entry.title}（{entry.start_ms / 1000}〜{entry.end_ms / 1000}秒）
                          {entry.note && <p>{entry.note}</p>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                {!!bundle.groups.length && (
                  <details>
                    <summary>Shelfの内容を見る</summary>
                    <ul>
                      {bundle.groups.map((entry) => (
                        <li key={entry.key}>
                          {entry.header_jpeg && (
                            <img
                              src={`data:image/jpeg;base64,${entry.header_jpeg}`}
                              alt={`${entry.name}の共有ヘッダー`}
                              style={{ maxWidth: 160, maxHeight: 100 }}
                            />
                          )}
                          {entry.name}（リンク{entry.links.length}件・Cell{entry.cells.length}件）
                          {entry.description && <p>{entry.description}</p>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
              {mode === 'export' ? (
                <>
                  <p>
                    リンク先の公開範囲は自動判定できません。共有してよい投稿・タイトル・タグ・メモか確認してください。ファイルを渡した後は回収できません。
                  </p>
                  {!!bundle.links.length && (
                    <label className="share-check">
                      <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
                      表示した内容を共有形式にしてもよいことを確認しました
                    </label>
                  )}
                  {!bundle.links.length && <p>共有できる外部リンクがありません。</p>}
                  <div className="modal-actions">
                    <button
                      className="button primary"
                      disabled={!agreed || !bundle.links.length}
                      onClick={download}
                    >
                      <Download size={16} />
                      ファイルを保存
                    </button>

                    <button
                      className="button secondary"
                      disabled={!agreed || !bundle.links.length}
                      onClick={copy}
                    >
                      <Copy size={16} />
                      共有データをコピー
                    </button>
                  </div>
                  <button
                    className="button secondary"
                    disabled={!agreed || !bundle.links.length}
                    onClick={copyShareUrl}
                  >
                    <Copy size={16} />
                    SNS用URLをコピー
                  </button>
                  <p className="muted">
                    短いリンク集はSNS用URLを投稿できます。データはURL内に含まれ、窓口サーバーには保存しません。URLを知っている人は内容を閲覧できます。
                  </p>
                  <p className="muted">
                    メール・LINEなどは保存したファイルを添付します。Xなどでファイルを添付できない場合は、自分で用意したファイルの公開URLを投稿してください。文字数制限で共有データを途中で切らないでください。
                  </p>
                </>
              ) : (
                incoming &&
                !incoming.duplicate && (
                  <>
                    <p>
                      リンク先にはまだ接続していません。画像は含まれないため、受け取った側では標準の表示になります。確認したタイトル・タグ・メモ・区間を自分のライブラリへ追加します。
                    </p>
                    <label className="share-check">
                      <input
                        type="checkbox"
                        checked={agreed}
                        disabled={busy}
                        onChange={(e) => setAgreed(e.target.checked)}
                      />
                      この内容を読み込んでよいことを確認しました
                    </label>
                    <div className="modal-actions">
                      <button className="button primary" disabled={!agreed || busy} onClick={apply}>
                        リンク集を追加
                      </button>
                    </div>
                  </>
                )
              )}
            </>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {result && <p role="status">{result}</p>}
        </div>
      </Modal>
    </>
  );
}

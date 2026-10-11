'use client';
import { useState } from 'react';
import { Link2, UploadCloud, CheckCircle2, ExternalLink, Loader2 } from 'lucide-react';
import { api, ImportResult } from '@/lib/api';
import { Uploader } from './upload';
import { ShelfGroup, destinationData } from '@/lib/groups';
import { DestinationPicker } from './destination-picker';

interface Result {
  url: string;
  result?: ImportResult;
  error?: string;
}
export function AddMedia({
  onComplete,
  onOpen,
  groups,
  destination,
  onDestinationChange,
  onCreateShelf,
}: {
  onComplete: () => void;
  onOpen: (id: string, start?: number) => void;
  groups: ShelfGroup[];
  destination: string;
  onDestinationChange: (value: string) => void;
  onCreateShelf: () => void;
}) {
  const [method, setMethod] = useState('link');
  const [links, setLinks] = useState('');
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [fileBusy, setFileBusy] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [error, setError] = useState('');
  const urls = links
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  async function add() {
    if (busy) return;
    if (!urls.length || urls.length > 20) {
      setError('1〜20件の共有リンクを、1行に1つずつ貼ってください。');
      return;
    }
    setBusy(true);
    setError('');
    setResults([]);
    const failed: string[] = [];
    for (const url of urls) {
      try {
        const result = await api<ImportResult>('/imports', {
          method: 'POST',
          body: JSON.stringify({
            url,
            title: urls.length === 1 ? title || undefined : undefined,
            ...destinationData(destination),
          }),
        });
        setResults((all) => [...all, { url, result }]);
        onComplete();
      } catch (e) {
        failed.push(url);
        setResults((all) => [...all, { url, error: (e as Error).message }]);
      }
    }
    setLinks(failed.join('\n'));
    if (!failed.length) setTitle('');
    setBusy(false);
  }
  return (
    <div className="add-media">
      <DestinationPicker
        groups={groups}
        value={destination}
        onChange={onDestinationChange}
        onCreate={onCreateShelf}
        disabled={busy || fileBusy}
      />
      <div className="add-methods" role="tablist" aria-label="追加方法">
        {(
          [
            ['link', 'リンクを貼る', Link2],
            ['file', 'ファイルを追加', UploadCloud],
          ] as const
        ).map(([value, label, Icon], index) => (
          <button
            key={value}
            id={`add-tab-${value}`}
            role="tab"
            aria-selected={method === value}
            aria-controls={`add-panel-${value}`}
            tabIndex={method === value ? 0 : -1}
            className={method === value ? 'active' : ''}
            disabled={busy || fileBusy}
            onClick={() => setMethod(value)}
            onKeyDown={(e) => {
              if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
              e.preventDefault();
              const next =
                e.key === 'Home' ? 'link' : e.key === 'End' ? 'file' : index === 0 ? 'file' : 'link';
              setMethod(next);
              document.getElementById(`add-tab-${next}`)?.focus();
            }}
          >
            <Icon size={17} />
            {label}
          </button>
        ))}
      </div>
      <section id="add-panel-link" role="tabpanel" aria-labelledby="add-tab-link" hidden={method !== 'link'}>
        <form
          className="link-adder form"
          onSubmit={(e) => {
            e.preventDefault();
            void add();
          }}
        >
          <div className="link-heading">
            <span className="upload-symbol">
              <Link2 size={29} />
            </span>
            <div>
              <h2>見つけた動画を、ひとまとめに。</h2>
              <p>YouTube · X · Instagram · TikTok</p>
            </div>
          </div>
          <label>
            動画・投稿の共有リンク
            <textarea
              rows={3}
              value={links}
              onChange={(e) => setLinks(e.target.value)}
              required
              disabled={busy}
              maxLength={42000}
              placeholder={'共有メニューでコピーしたリンクを貼り付ける\n複数あるときは、1行に1つずつ'}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
          </label>
          <small className="muted">
            最大20件。ホームやプロフィールではなく、動画・投稿のリンクを使ってください。
          </small>
          {urls.length <= 1 && (
            <label>
              タイトル（任意）
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={busy}
                maxLength={200}
                placeholder="あとで見つけやすい名前"
              />
            </label>
          )}
          <div className="link-help">
            <p>
              各サービスの「共有」→「リンクをコピー」で追加できます。Instagramは投稿やリールを開いてからコピーしてください。
            </p>
            <p>
              リンクとして保存します。非公開・削除済み・ログインが必要な動画は、元のサービスで確認できます。メモ・タグ・お気に入り・整理に使えます。
            </p>
          </div>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button className="button primary" disabled={busy || !urls.length}>
              {busy ? <Loader2 className="spin" size={17} /> : <Link2 size={17} />}
              {busy ? '追加しています…' : urls.length > 1 ? `${urls.length}件を追加` : 'ライブラリに追加'}
            </button>
          </div>
        </form>
        {results.length > 0 && (
          <div className="link-results" aria-live="polite">
            <h3>
              {results.filter((r) => r.result?.created).length}件追加 ·{' '}
              {results.filter((r) => r.result && !r.result.created).length}件保存済み ·{' '}
              {results.filter((r) => r.error).length}件未追加
            </h3>
            {results.map((r, index) => (
              <div className="link-result" key={index}>
                {r.result ? <CheckCircle2 size={19} className="success" /> : <Link2 size={19} />}
                <div>
                  <strong>{r.result?.media.title || r.url}</strong>
                  <p>
                    {r.error || (r.result?.created ? '追加しました' : 'すでに保存されています')}
                    {r.result && !r.result.metadata_available ? '。タイトルは詳細画面で編集できます。' : ''}
                  </p>
                </div>
                {r.result && (
                  <button
                    className="text-button"
                    onClick={() => onOpen(r.result!.media.id, r.result!.start_ms)}
                  >
                    <ExternalLink size={15} />
                    開く
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      <section id="add-panel-file" role="tabpanel" aria-labelledby="add-tab-file" hidden={method !== 'file'}>
        <Uploader onComplete={onComplete} destination={destination} onBusyChange={setFileBusy} />
      </section>
    </div>
  );
}

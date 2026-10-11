'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, ExternalLink, FolderPlus, Link2, Pencil, Trash2, UploadCloud } from 'lucide-react';
import { api, Cell, csrf, Media, time } from '@/lib/api';
import { Modal } from './ui/dialog';
import { Confirm } from './ui/confirm';
import { CellPlayer } from './cell-player';
import { LinkCellPlayer } from './link-cell-player';
import { TrimTimeline } from './trim-timeline';
import type { PublicPreview } from './public-preview';

export function CellDetail({
  id,
  onClose,
  onChanged,
  notify,
  onOrganize,
  onOpenMedia,
}: {
  id: string;
  onClose: () => void;
  onChanged: () => void;
  notify: (s: string) => void;
  onOrganize: (cell: Cell) => void;
  onOpenMedia: (id: string) => void;
}) {
  const cell = useQuery({ queryKey: ['cell-detail', id], queryFn: () => api<Cell>('/cells/' + id) });
  const media = useQuery({
    queryKey: ['cell-media', cell.data?.media_id],
    queryFn: () => api<Media>('/media/' + cell.data!.media_id),
    enabled: !!cell.data,
    refetchInterval: (q) => (q.state.data?.status === 'PROCESSING' ? 1000 : false),
  });
  const [editing, setEditing] = useState(false),
    [deleting, setDeleting] = useState(false);
  const [draft, setDraft] = useState({ title: '', start: 0, end: 1, note: '', tags: '' });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [actualDuration, setActualDuration] = useState<number>();
  const c = cell.data,
    m = media.data;
  const managed = m?.storage_mode === 'MANAGED';
  const playableLink = !!m && ['youtube', 'tiktok'].includes(m.source.provider);
  const preview = useQuery({
    queryKey: ['cell-preview', m?.id],
    queryFn: ({ signal }) => api<PublicPreview>(`/media/${m!.id}/reference-preview/info`, { signal }),
    enabled: !!m && !managed,
    retry: false,
    refetchOnWindowFocus: false,
  });
  async function download() {
    if (!c) return;
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/v1/cells/${c.id}/clip`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrf() },
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error?.message ?? 'クリップを書き出せませんでした。');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = c.title + '.mp4';
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify('Cellの範囲だけをMP4で保存しました');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function attach(file?: File) {
    if (!file || !m || busy) return;
    if (file.size > 256 * 1024 ** 2 || !/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(file.name)) {
      setError('256 MB以下のMOV・MP4などの動画ファイルを選んでください。');
      return;
    }
    const body = new FormData();
    body.append('file', file);
    body.append('reference_id', m.id);
    setBusy(true);
    setError('');
    try {
      await api('/media', { method: 'POST', body, headers: { 'Idempotency-Key': crypto.randomUUID() } });
      await media.refetch();
      onChanged();
      notify('動画を追加しました。Cellの再生を準備しています');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (!c) return;
    if (
      !Number.isFinite(draft.start) ||
      !Number.isFinite(draft.end) ||
      draft.start < 0 ||
      draft.start >= draft.end ||
      draft.end > editorDuration ||
      draft.end - draft.start > 300
    ) {
      setError('動画の長さ以内で、5分以下の区間を選んでください。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api('/cells/' + c.id, {
        method: 'PATCH',
        body: JSON.stringify({
          title: draft.title.trim(),
          note: draft.note,
          tags: [
            ...new Set(
              draft.tags
                .split(/[,、]/)
                .map((tag) => tag.trim())
                .filter(Boolean),
            ),
          ].slice(0, 20),
          start_ms: Math.round(draft.start * 1000),
          end_ms: Math.round(draft.end * 1000),
        }),
      });
      await cell.refetch();
      setEditing(false);
      onChanged();
      notify('Cellを更新しました');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const editorDuration = managed
    ? (m?.duration_ms ?? 1000) / 1000
    : preview.data
      ? preview.data.duration_ms / 1000
      : (actualDuration ?? Math.max(60, draft.end));
  const originalUrl =
    m?.source.url && m.source.provider === 'youtube' && c
      ? m.source.url + '&t=' + Math.floor(c.start_ms / 1000) + 's'
      : m?.source.url;
  return (
    <Modal
      open
      onClose={onClose}
      title={c?.title ?? 'Cellを読み込み中…'}
      wide
      className="cell-detail"
      description={c ? time(c.end_ms - c.start_ms, true) + ' · 保存したCell' : undefined}
    >
      {cell.isError || media.isError ? (
        <p className="error-message" role="alert">
          {cell.error?.message || media.error?.message}
        </p>
      ) : !c || !m ? (
        <div className="skeleton player-skeleton" />
      ) : (
        <div className="cell-detail-content">
          {editing ? (
            <form
              id="saved-cell-editor"
              className="form"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              {managed && m.assets.preview && draft.start < draft.end && draft.end <= editorDuration && (
                <CellPlayer src={m.assets.preview} start={draft.start} end={draft.end} />
              )}
              <TrimTimeline
                source={managed ? m.assets.preview : preview.data?.url}
                cover={m.assets.thumbnail || m.source.thumbnail_url || undefined}
                duration={editorDuration}
                start={draft.start}
                end={draft.end}
                disabled={busy}
                onChange={(start, end) => setDraft({ ...draft, start, end })}
              />
              <details className="trim-precision">
                <summary>時刻を細かく指定</summary>
                <div className="form-grid">
                  <label>
                    開始（秒）
                    <input
                      type="number"
                      min={0}
                      max={editorDuration}
                      step={0.001}
                      value={draft.start}
                      onChange={(e) => setDraft({ ...draft, start: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    終了（秒）
                    <input
                      type="number"
                      min={0.001}
                      max={editorDuration}
                      step={0.001}
                      value={draft.end}
                      onChange={(e) => setDraft({ ...draft, end: Number(e.target.value) })}
                    />
                  </label>
                </div>
              </details>
              <label>
                タイトル
                <input
                  required
                  maxLength={200}
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                />
              </label>
              <details>
                <summary>メモ・タグを編集</summary>
                <div className="form">
                  <label>
                    メモ
                    <textarea
                      maxLength={10000}
                      value={draft.note}
                      onChange={(e) => setDraft({ ...draft, note: e.target.value })}
                    />
                  </label>
                  <label>
                    タグ
                    <input
                      value={draft.tags}
                      onChange={(e) => setDraft({ ...draft, tags: e.target.value })}
                    />
                  </label>
                </div>
              </details>
              <div className="form-actions">
                <button
                  type="button"
                  className="text-button"
                  disabled={busy}
                  onClick={() => {
                    setEditing(false);
                    setError('');
                  }}
                >
                  キャンセル
                </button>
                <button className="button primary" disabled={busy}>
                  変更を保存
                </button>
              </div>
            </form>
          ) : managed && m.status === 'READY' && m.assets.preview ? (
            <CellPlayer
              key={c.start_ms + ':' + c.end_ms}
              src={m.assets.preview}
              start={c.start_ms / 1000}
              end={c.end_ms / 1000}
            />
          ) : managed ? (
            <div className="inline-empty">
              <h3>Cellの再生を準備しています</h3>
              <p>この画面を閉じても処理は続きます。</p>
            </div>
          ) : preview.data ? (
            <CellPlayer
              key={c.start_ms + ':' + c.end_ms}
              src={preview.data.url}
              start={c.start_ms / 1000}
              end={c.end_ms / 1000}
            />
          ) : playableLink ? (
            <LinkCellPlayer
              key={c.start_ms + ':' + c.end_ms}
              media={m}
              start={c.start_ms / 1000}
              end={c.end_ms / 1000}
              onDuration={setActualDuration}
            />
          ) : (
            <div className="cell-link-unavailable">
              {m.assets.thumbnail ? <img src={m.assets.thumbnail} alt="" /> : <Link2 size={32} />}
              <h3>動画ファイルを追加して、このCellを再生</h3>
              <p>
                {m.source.label}
                のリンクは区間指定の再生に対応していません。動画ファイルを追加すると、保存した範囲だけを再生できます。
              </p>
            </div>
          )}
          {!editing && (
            <>
              <div className="cell-detail-actions">
                {managed && (
                  <button
                    className="button primary"
                    disabled={busy || m.status !== 'READY'}
                    onClick={() => void download()}
                  >
                    <Download size={16} />
                    {busy ? '書き出し中…' : 'CellをMP4で保存'}
                  </button>
                )}
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => {
                    const invalid =
                      !managed && actualDuration !== undefined && c.end_ms / 1000 > actualDuration + 0.1;
                    setDraft({
                      title: c.title,
                      start: invalid ? 0 : c.start_ms / 1000,
                      end: invalid ? actualDuration! : c.end_ms / 1000,
                      note: c.note,
                      tags: c.tags.join(', '),
                    });
                    setEditing(true);
                    setError(
                      invalid
                        ? '元の保存範囲が動画の長さを超えていました。実際の動画から選び直してください。'
                        : '',
                    );
                  }}
                >
                  <Pencil size={16} />
                  範囲・情報を編集
                </button>
                <button className="button secondary" onClick={() => onOrganize(c)}>
                  <FolderPlus size={16} />
                  Shelfに整理
                </button>
              </div>
              {!managed && (
                <div className="cell-link-help">
                  <p>
                    {playableLink
                      ? '元動画ファイルを追加すると、外部サービスに接続せずにこの範囲だけを再生・書き出しできます。'
                      : 'Cellのタイトル・保存範囲・Shelfはそのまま引き継ぎます。'}
                  </p>
                  <div className="cell-detail-actions">
                    <label className={`button ${playableLink ? 'secondary' : 'primary'} cell-file-label`}>
                      <UploadCloud size={16} />
                      {busy ? '追加しています…' : '動画ファイルを追加'}
                      <input
                        type="file"
                        disabled={busy}
                        accept=".mp4,.mov,.m4v,.webm,.mkv,.avi"
                        onChange={(e) => {
                          void attach(e.target.files?.[0]);
                          e.target.value = '';
                        }}
                      />
                    </label>
                    <a
                      className="button secondary"
                      href={originalUrl || undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink size={16} />
                      {m.source.label}で開く
                    </a>
                  </div>
                </div>
              )}
              {c.note && <p className="detail-note">{c.note}</p>}
              {!!c.tags.length && (
                <div className="tags">
                  {c.tags.map((tag) => (
                    <span key={tag}>#{tag}</span>
                  ))}
                </div>
              )}
              <div className="cell-origin">
                <button className="text-button" onClick={() => onOpenMedia(m.id)}>
                  元動画を開く
                </button>
                <span>
                  {time(c.start_ms, true)} — {time(c.end_ms, true)}
                </span>
                <button
                  className="icon-button"
                  aria-label="Cellを削除"
                  disabled={busy}
                  onClick={() => setDeleting(true)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </>
          )}
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
      <Confirm
        open={deleting}
        onClose={() => setDeleting(false)}
        title="Cellを削除しますか？"
        description="このCellだけを削除します。元動画は残ります。"
        pending={busy}
        onConfirm={async () => {
          setBusy(true);
          setError('');
          try {
            await api('/cells/' + id, { method: 'DELETE' });
            onChanged();
            onClose();
            notify('Cellを削除しました');
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      />
    </Modal>
  );
}

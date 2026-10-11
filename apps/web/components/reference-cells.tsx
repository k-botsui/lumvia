'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, FolderPlus, Link2, Pencil, Play, Scissors, Trash2 } from 'lucide-react';
import { api, Cell, Media, Page, time } from '@/lib/api';
import { TrimTimeline } from './trim-timeline';
import { Confirm } from './ui/confirm';

export type LinkRange = { start: number; end: number };
export function ReferenceCells({
  media,
  initialTime,
  initialEnd,
  actualDuration,
  previewSource,
  previewLoading,
  previewError,
  onRetryPreview,
  position,
  onPreview,
  onInspect,
  onEditing,
  onChanged,
  onOrganize,
  onOpenCell,
  notify,
}: {
  media: Media;
  initialTime: number;
  initialEnd?: number;
  actualDuration?: number;
  previewSource?: string;
  previewLoading: boolean;
  previewError: string;
  onRetryPreview: () => void;
  position: number;
  onPreview: (range: LinkRange) => void;
  onInspect: (position: number) => void;
  onEditing: (active: boolean) => void;
  onChanged: () => void;
  onOrganize: (cell: Cell) => void;
  onOpenCell: (cell: Cell) => void;
  notify: (message: string) => void;
}) {
  const cells = useQuery({
    queryKey: ['media-cells', media.id],
    queryFn: () => api<Page<Cell>>(`/cells?media_id=${media.id}&limit=100`),
  });
  const [editor, setEditor] = useState<{ cell?: Cell } | null>(null);
  const [range, setRange] = useState<LinkRange>({ start: 0, end: 10 });
  const [extent, setExtent] = useState(60);
  const [title, setTitle] = useState(''),
    [note, setNote] = useState('');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [deleting, setDeleting] = useState<Cell | null>(null);
  const playable = !!previewSource || ['youtube', 'tiktok'].includes(media.source.provider);
  const awaitingDuration = media.source.provider === 'tiktok' && !actualDuration;
  const duration = actualDuration ?? extent;
  const safeStart = Math.min(range.start, Math.max(0, duration - 0.1));
  const safeEnd = Math.min(duration, Math.max(safeStart + 0.1, range.end));
  function edit(cell?: Cell) {
    const start = Math.max(0, Math.min((cell?.start_ms ?? initialTime ?? 0) / 1000, 3599));
    const end = Math.min(3600, (cell?.end_ms ?? initialEnd ?? (start + 10) * 1000) / 1000);
    setRange({ start, end: Math.max(start + 0.1, end) });
    setExtent(Math.max(60, end, start + 60));
    setTitle(cell?.title ?? `${media.title.slice(0, 160)} · ${time(start * 1000)}`);
    setNote(cell?.note ?? '');
    setEditor({ cell });
    setError('');
    onEditing(true);
    if (awaitingDuration) onInspect(0);
  }
  function change(start: number, end: number, at = start) {
    setRange({ start, end });
    if (playable) onInspect(Math.max(0, Math.min(duration - 0.025, at)));
  }
  async function save() {
    setBusy(true);
    setError('');
    try {
      const values = {
        title: title.trim(),
        note,
        tags: editor?.cell?.tags ?? [],
        start_ms: Math.round(safeStart * 1000),
        end_ms: Math.round(safeEnd * 1000),
      };
      const saved = await api<Cell>(editor?.cell ? `/cells/${editor.cell.id}` : '/cells', {
        method: editor?.cell ? 'PATCH' : 'POST',
        body: JSON.stringify(editor?.cell ? values : { ...values, media_id: media.id }),
      });
      await cells.refetch();
      onChanged();
      setEditor(null);
      onEditing(false);
      notify('Cellを保存しました');
      onOpenCell(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="reference-cells">
      <div className="section-heading">
        <h3>
          {editor ? (
            '動画を切り取る'
          ) : (
            <>
              保存したCell <small>{cells.data?.total ?? 0}</small>
            </>
          )}
        </h3>
        {!editor && (
          <button className="button secondary compact" disabled={busy} onClick={() => edit()}>
            <Scissors size={16} />
            区間を切り取る
          </button>
        )}
      </div>
      {editor && (
        <form
          className="form reference-trimmer"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          {previewLoading && (
            <p className="preview-loading" role="status">
              公開動画から場面画像を準備しています…
            </p>
          )}
          {previewError && (
            <div className="reference-help">
              <p>{previewError}</p>
              <button type="button" className="text-button" onClick={onRetryPreview}>
                場面画像を再読み込み
              </button>
            </div>
          )}
          {awaitingDuration && (
            <div className="reference-help">
              <p>動画の長さを読み込んでいます。TikTok内の再生ボタンを押すと取得できます。</p>
              <button type="button" className="button secondary" onClick={() => onInspect(0)}>
                動画の長さを読み込む
              </button>
            </div>
          )}
          {!actualDuration && !awaitingDuration && (
            <label>
              タイムラインの範囲（秒）
              <input
                type="number"
                min={1}
                max={3600}
                step={1}
                value={extent}
                onChange={(e) => {
                  const value = Number(e.target.value);
                  if (Number.isFinite(value)) setExtent(Math.max(1, Math.min(3600, value)));
                }}
              />
              <small className="muted">
                リンクから動画の長さを取得できない場合は、必要な範囲を指定してください。
              </small>
            </label>
          )}
          {!awaitingDuration && (
            <TrimTimeline
              source={previewSource}
              duration={duration}
              start={safeStart}
              end={safeEnd}
              disabled={busy || previewLoading}
              position={position}
              livePreview={playable}
              onChange={change}
            />
          )}
          {playable && !awaitingDuration && (
            <div className="trim-scene-actions">
              <button type="button" className="button secondary compact" onClick={() => onInspect(safeStart)}>
                開始の場面を確認
              </button>
              <button
                type="button"
                className="button secondary compact"
                onClick={() => onInspect(Math.max(safeStart, safeEnd - 0.025))}
              >
                終了の場面を確認
              </button>
              <button
                type="button"
                className="button secondary compact"
                onClick={() => onPreview({ start: safeStart, end: safeEnd })}
              >
                <Play size={15} />
                区間を再生
              </button>
            </div>
          )}
          {!awaitingDuration && (
            <details className="trim-precision">
              <summary>時刻を細かく指定</summary>
              <div className="form-grid">
                <label>
                  開始（秒）
                  <input
                    type="number"
                    min={0}
                    max={duration}
                    step={0.001}
                    value={safeStart}
                    onChange={(e) => change(Number(e.target.value) || 0, safeEnd)}
                  />
                </label>
                <label>
                  終了（秒）
                  <input
                    type="number"
                    min={0.001}
                    max={duration}
                    step={0.001}
                    value={safeEnd}
                    onChange={(e) =>
                      change(safeStart, Number(e.target.value) || 0.1, Number(e.target.value) || 0.1)
                    }
                  />
                </label>
              </div>
            </details>
          )}
          <details className="trim-precision trim-metadata">
            <summary>名前・メモを編集</summary>
            <div className="form">
              <label>
                タイトル
                <input value={title} required maxLength={200} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <label>
                メモ
                <textarea value={note} rows={2} maxLength={10000} onChange={(e) => setNote(e.target.value)} />
              </label>
            </div>
          </details>
          <details className="trim-precision">
            <summary>リンクの切り取りについて</summary>
            <p className="reference-help">
              公開動画は場面を選ぶために一時取得します。10分・32
              MBまでで、一時データは30分後に削除されます。リンクとCellの区間は残ります。MP4書き出しには元動画ファイルを追加してください。
              {media.source.provider === 'tiktok' &&
                'リンクの区間再生は、停止位置が少しずれる場合があります。'}
              {media.source.provider === 'youtube' &&
                'YouTubeの再生位置は秒単位のため、開始位置が少しずれる場合があります。'}
              {!playable && `${media.source.label}は区間の指定再生に対応していません。`}
            </p>
          </details>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() => {
                setEditor(null);
                onEditing(false);
              }}
            >
              キャンセル
            </button>
            <button className="button primary" disabled={busy || awaitingDuration || previewLoading}>
              <Check size={16} />
              {busy ? '保存中…' : 'Cellを保存'}
            </button>
          </div>
        </form>
      )}
      <div className="cell-rows">
        {cells.data?.items.map((cell) => (
          <div className="cell-row" key={cell.id}>
            <button
              className="cell-play"
              aria-label={`${cell.title}${playable ? 'を再生' : 'を開く'}`}
              onClick={() => onOpenCell(cell)}
            >
              {playable ? <Play size={16} /> : <Link2 size={16} />}
            </button>
            <div className="cell-description">
              <button onClick={() => onOpenCell(cell)}>{cell.title}</button>
              <span>
                {time(cell.start_ms, true)} — {time(cell.end_ms, true)} · リンクの区間
              </span>
            </div>
            <button
              className="icon-button"
              aria-label={`${cell.title}の整理先を編集`}
              onClick={() => onOrganize(cell)}
            >
              <FolderPlus size={16} />
            </button>
            <button className="icon-button" aria-label={`${cell.title}を編集`} onClick={() => edit(cell)}>
              <Pencil size={16} />
            </button>
            <button
              className="icon-button"
              aria-label={`${cell.title}を削除`}
              onClick={() => setDeleting(cell)}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>
      {cells.isError && <p className="error-message">{cells.error.message}</p>}
      {!cells.data?.total && !editor && <p className="muted">残したい区間を選んで保存できます。</p>}
      <Confirm
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Cellを削除しますか？"
        description="この区間の保存を削除します。元のリンクは残ります。"
        pending={busy}
        onConfirm={async () => {
          if (!deleting) return;
          setBusy(true);
          try {
            await api(`/cells/${deleting.id}`, { method: 'DELETE' });
            setDeleting(null);
            await cells.refetch();
            onChanged();
            notify('Cellを削除しました');
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      />
      {error && !editor && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

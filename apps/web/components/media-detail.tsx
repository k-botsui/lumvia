'use client';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  BookmarkPlus,
  Play,
  Scissors,
  Pencil,
  Trash2,
  FolderPlus,
  Download,
  Heart,
  ScanLine,
  Loader2,
  Check,
  Info,
} from 'lucide-react';
import { Analysis, api, bytes, Cell, csrf, Event, Media, Page, time } from '@/lib/api';
import { Modal } from './ui/dialog';
import { Confirm } from './ui/confirm';
import { ReferenceDetail } from './reference-detail';
import { CoverPicker } from './cover-picker';
import { TrimTimeline } from './trim-timeline';

const cellSchema = z
  .object({
    title: z.string().trim().min(1, 'タイトルを入力してください。').max(200),
    start: z.number().min(0),
    end: z.number().positive(),
    note: z.string().max(10000),
    tags: z.string(),
  })
  .refine((v) => v.end > v.start, { message: '終了時刻は開始時刻より後にしてください。', path: ['end'] });
type CellForm = z.infer<typeof cellSchema>;
function splitTags(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[,、]/)
        .map((s) => s.trim())
        .filter(Boolean),
    ),
  ).slice(0, 20);
}
export function MediaDetail({
  id,
  initialTime,
  initialEnd,
  onClose,
  onChanged,
  notify,
  onOrganize,
  onOpenCell,
}: {
  id: string;
  initialTime: number;
  initialEnd?: number;
  onClose: () => void;
  onChanged: () => void;
  notify: (s: string) => void;
  onOrganize: (m: Media | Cell) => void;
  onOpenCell: (cell: Cell) => void;
}) {
  const media = useQuery({
    queryKey: ['media-detail', id],
    queryFn: () => api<Media>('/media/' + id),
    refetchInterval: (q) => (q.state.data?.status === 'PROCESSING' ? 2000 : false),
  });
  const cells = useQuery({
    queryKey: ['media-cells', id],
    queryFn: () => api<Page<Cell>>('/cells?media_id=' + id + '&limit=100'),
    enabled: media.data?.storage_mode === 'MANAGED',
  });
  const [analysisOffset, setAnalysisOffset] = useState(0);
  const analysis = useQuery({
    queryKey: ['analysis', id, analysisOffset],
    queryFn: () => api<Analysis>(`/media/${id}/analysis?offset=${analysisOffset}`),
    enabled: media.data?.storage_mode === 'MANAGED',
    refetchInterval: (q) =>
      q.state.data?.runs.some((r) => ['PENDING', 'RUNNING'].includes(r.status)) ? 2000 : false,
  });
  const video = useRef<HTMLVideoElement>(null);
  const stopAt = useRef<number | null>(null);
  const rangeVideo = useRef<HTMLVideoElement>(null);
  const [position, setPosition] = useState(0);
  const [tab, setTab] = useState('cells');
  const [editor, setEditor] = useState<{ cell?: Cell; event?: Event } | null>(null);
  const [metadata, setMetadata] = useState(false);
  const [deleting, setDeleting] = useState<Media | Cell | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [trimPosition, setTrimPosition] = useState(0);
  const [runDeleting, setRunDeleting] = useState<string | null>(null);
  const form = useForm<CellForm>({
    resolver: zodResolver(cellSchema),
    defaultValues: { title: '', start: 0, end: 10, note: '', tags: '' },
  });
  const watched = useWatch({ control: form.control }) as CellForm;
  const m = media.data;
  function refresh() {
    onChanged();
    void media.refetch();
    if (media.data?.storage_mode === 'MANAGED') {
      void cells.refetch();
      void analysis.refetch();
    }
  }
  async function act(action: () => Promise<unknown>, success?: string) {
    setBusy(true);
    setError('');
    try {
      await action();
      refresh();
      if (success) notify(success);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  function seek(start: number, end?: number) {
    if (!video.current) return;
    video.current.currentTime = start / 1000;
    stopAt.current = end ?? null;
    void video.current.play().catch(() => {});
  }
  function initializeRange(el: HTMLVideoElement) {
    const start = Number.isFinite(initialTime) ? initialTime / 1000 : 0;
    el.currentTime = Math.max(0, Math.min(start, el.duration));
    stopAt.current = initialEnd !== undefined && Number.isFinite(initialEnd) ? initialEnd : null;
  }
  function editCell(cell?: Cell, event?: Event) {
    if (!m) return;
    video.current?.pause();
    const start =
      cell?.start_ms ??
      event?.start_ms ??
      Math.min(Math.round(position * 1000), Math.max(0, m.duration_ms - 1000));
    const end = cell?.end_ms ?? Math.min(event?.end_ms ?? m.duration_ms, start + 300000);
    form.reset({
      title: cell?.title ?? event?.label ?? `${m.title.slice(0, 160)} · ${time(start)}`,
      start: start / 1000,
      end: end / 1000,
      note: cell?.note ?? '',
      tags: cell?.tags.join(', ') ?? '',
    });
    setTrimPosition(start / 1000);
    setEditor({ cell, event });
    setError('');
  }
  async function saveCell(values: CellForm) {
    const saved: { cell?: Cell } = {};
    const data = {
      title: values.title,
      start_ms: Math.round(values.start * 1000),
      end_ms: Math.round(values.end * 1000),
      note: values.note,
      tags: splitTags(values.tags),
    };
    if (
      await act(async () => {
        saved.cell = await api<Cell>(editor?.cell ? '/cells/' + editor.cell.id : '/cells', {
          method: editor?.cell ? 'PATCH' : 'POST',
          body: JSON.stringify(editor?.cell ? data : { ...data, media_id: id, event_id: editor?.event?.id }),
        });
      }, 'Cellを保存しました')
    ) {
      setEditor(null);
      if (saved.cell) onOpenCell(saved.cell);
    }
  }
  async function downloadClip(cell: Cell) {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/v1/cells/${cell.id}/clip`, {
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
      link.download = cell.title + '.mp4';
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify('クリップを書き出しました');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    const el = video.current;
    if (el && (initialTime || initialEnd !== undefined)) {
      const ready = () => {
        el.currentTime = Math.max(0, Math.min(initialTime / 1000, el.duration));
        stopAt.current = initialEnd ?? null;
      };
      el.addEventListener('loadedmetadata', ready);
      if (el.readyState >= 1) ready();
      return () => el.removeEventListener('loadedmetadata', ready);
    }
  }, [initialTime, initialEnd, m?.assets.preview]);
  if (m?.storage_mode === 'REFERENCE')
    return (
      <ReferenceDetail
        media={m}
        initialTime={initialTime}
        initialEnd={initialEnd}
        onClose={onClose}
        onChanged={refresh}
        notify={notify}
        onOrganize={onOrganize}
        onOpenCell={onOpenCell}
      />
    );
  return (
    <Modal open onClose={onClose} title={m?.title ?? '動画を読み込み中…'} wide>
      {media.isError ? (
        <div className="error-message" role="alert">
          {media.error.message}
          <button onClick={() => media.refetch()}>再試行</button>
        </div>
      ) : !m ? (
        <div className="skeleton player-skeleton" />
      ) : (
        <>
          <div className="detail-columns">
            <div className="detail-main">
              <div className="video-frame">
                {m.assets.preview && m.status === 'READY' ? (
                  <video
                    ref={video}
                    controls
                    playsInline
                    preload="metadata"
                    poster={m.assets.thumbnail}
                    onLoadedMetadata={(event) => initializeRange(event.currentTarget)}
                    onTimeUpdate={() => {
                      const el = video.current;
                      if (el) {
                        setPosition(el.currentTime);
                        if (stopAt.current !== null && el.currentTime * 1000 >= stopAt.current) {
                          el.pause();
                          el.currentTime = stopAt.current / 1000;
                          stopAt.current = null;
                        }
                      }
                    }}
                  >
                    <source src={m.assets.preview} type="video/mp4" />
                  </video>
                ) : (
                  <div className="video-wait">
                    {m.status === 'PROCESSING' ? <Loader2 className="spin" size={36} /> : <Info size={36} />}
                    <h3>
                      {m.status === 'PROCESSING' ? '再生の準備をしています' : '動画を準備できませんでした'}
                    </h3>
                    <p>
                      {m.status === 'PROCESSING'
                        ? 'この画面を閉じても処理は続きます。'
                        : '進捗一覧で詳細を確認し、再試行できます。'}
                    </p>
                  </div>
                )}
              </div>
              <div className="video-tools">
                <div>
                  <span className="badge">{m.storage_mode === 'MANAGED' ? '保存済み' : '参照'}</span>
                  <span className="muted">
                    {time(m.duration_ms)} · {m.width} × {m.height} · {bytes(m.size_bytes)}
                  </span>
                </div>
                <button className="button primary" disabled={m.status !== 'READY'} onClick={() => editCell()}>
                  <Scissors size={17} />
                  Cellを作成
                </button>
              </div>
              <div className="detail-tabs" role="tablist" aria-label="動画の情報">
                {[
                  ['cells', '保存したCells', BookmarkPlus],
                  ['scenes', '見つかったシーン', ScanLine],
                ].map(([value, label, Icon]) => {
                  const I = Icon as typeof BookmarkPlus;
                  return (
                    <button
                      key={value as string}
                      role="tab"
                      id={`video-tab-${value}`}
                      aria-controls="video-tab-panel"
                      tabIndex={tab === value ? 0 : -1}
                      onKeyDown={(e) => {
                        const values = ['cells', 'scenes'];
                        const current = values.indexOf(value as string);
                        let next = current;
                        if (e.key === 'ArrowRight') next = (current + 1) % 2;
                        else if (e.key === 'ArrowLeft') next = (current + 1) % 2;
                        else if (e.key === 'Home') next = 0;
                        else if (e.key === 'End') next = 1;
                        else return;
                        e.preventDefault();
                        setTab(values[next]);
                        document.getElementById(`video-tab-${values[next]}`)?.focus();
                      }}
                      aria-selected={tab === value}
                      onClick={() => setTab(value as string)}
                      className={tab === value ? 'active' : ''}
                    >
                      <I size={17} />
                      {label as string}
                      {value === 'cells' && <span>{cells.data?.total ?? 0}</span>}
                    </button>
                  );
                })}
              </div>
              <div
                className="tab-content"
                role="tabpanel"
                id="video-tab-panel"
                aria-labelledby={`video-tab-${tab}`}
              >
                {tab === 'cells' &&
                  (cells.data?.items.length ? (
                    <>
                      <div className="cell-rows">
                        {cells.data.items.map((cell) => (
                          <div className="cell-row" key={cell.id}>
                            <button
                              className="cell-play"
                              onClick={() => onOpenCell(cell)}
                              aria-label={`${cell.title}を再生`}
                            >
                              <Play size={16} />
                            </button>
                            <div className="cell-description">
                              <button onClick={() => onOpenCell(cell)}>{cell.title}</button>
                              <span>
                                {time(cell.start_ms, true)} — {time(cell.end_ms, true)}
                                {cell.origin !== 'user' ? ' · 解析候補から保存' : ''}
                              </span>
                              {cell.tags.length > 0 && (
                                <small>{cell.tags.map((t) => '#' + t).join(' ')}</small>
                              )}
                            </div>
                            <button
                              className="icon-button"
                              aria-label={`${cell.title}をMP4で保存`}
                              disabled={busy}
                              onClick={() => void downloadClip(cell)}
                            >
                              <Download size={15} />
                            </button>
                            <button
                              className="icon-button"
                              aria-label={`${cell.title}を編集`}
                              onClick={() => editCell(cell)}
                            >
                              <Pencil size={15} />
                            </button>
                            <button
                              className="icon-button"
                              aria-label={`${cell.title}を整理`}
                              onClick={() => onOrganize(cell)}
                            >
                              <FolderPlus size={16} />
                            </button>
                            <button
                              className="icon-button"
                              aria-label={`${cell.title}を削除`}
                              onClick={() => setDeleting(cell)}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        ))}
                      </div>
                      {cells.data.total > 100 && (
                        <p className="muted">
                          先頭100件を表示しています。ライブラリの検索で他のCellも見つけられます。
                        </p>
                      )}
                    </>
                  ) : (
                    <div className="inline-empty">
                      <BookmarkPlus size={28} />
                      <h3>残しておきたい瞬間を、Cellに。</h3>
                      <p>開始と終了を選んで、動画の好きな部分を保存できます。</p>
                      <button
                        className="button secondary"
                        onClick={() => editCell()}
                        disabled={m.status !== 'READY'}
                      >
                        最初のCellを作成
                      </button>
                    </div>
                  ))}
                {tab === 'scenes' && (
                  <>
                    <div className="analysis-intro">
                      <p>映像の切り替わりを見つけ、保存する区間を提案します。</p>
                      <button
                        className="button secondary"
                        disabled={
                          busy ||
                          m.status !== 'READY' ||
                          analysis.data?.runs.some(
                            (r) => r.analyzer === 'scenes' && ['RUNNING', 'PENDING'].includes(r.status),
                          )
                        }
                        onClick={() =>
                          act(
                            () =>
                              api(`/media/${id}/analysis`, {
                                method: 'POST',
                                body: JSON.stringify({ analyzer: 'scenes' }),
                              }),
                            'シーンの解析を開始しました',
                          )
                        }
                      >
                        <ScanLine size={17} />
                        シーンを見つける
                      </button>
                    </div>
                    {analysis.data?.runs.some((r) => ['RUNNING', 'PENDING'].includes(r.status)) && (
                      <p className="processing-note">
                        <Loader2 size={16} className="spin" />
                        解析しています。このまま他の操作もできます。
                      </p>
                    )}
                    <div className="cell-rows">
                      {analysis.data?.events.map((event) => (
                        <div className="cell-row" key={event.id}>
                          <button
                            className="cell-play"
                            onClick={() => seek(event.start_ms, event.end_ms)}
                            aria-label={`${event.label}を再生`}
                          >
                            <Play size={16} />
                          </button>
                          <div className="cell-description">
                            <strong>{event.label}</strong>
                            <span>
                              {time(event.start_ms)} — {time(event.end_ms)} · 候補
                            </span>
                          </div>
                          <button
                            className="button compact secondary"
                            onClick={() => editCell(undefined, event)}
                          >
                            <BookmarkPlus size={15} />
                            Cellにする
                          </button>
                        </div>
                      ))}
                    </div>
                    {!analysis.data?.events.length && (
                      <p className="muted center">見つかった候補がここに表示されます。</p>
                    )}
                    {!!analysis.data?.runs.length && (
                      <details className="analysis-history">
                        <summary>解析履歴（{analysis.data.runs.length} / 10）</summary>
                        {analysis.data.runs.map((run) => (
                          <div key={run.id}>
                            <span>シーン · {new Date(run.created_at).toLocaleString('ja-JP')}</span>
                            <button
                              className="icon-button"
                              aria-label="この解析履歴を削除"
                              disabled={busy || ['PENDING', 'RUNNING'].includes(run.status)}
                              onClick={() => setRunDeleting(run.id)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        ))}
                      </details>
                    )}
                  </>
                )}
                {tab !== 'cells' && (analysisOffset > 0 || analysis.data?.has_more) && (
                  <div className="pagination">
                    <button
                      className="button secondary"
                      disabled={analysisOffset === 0}
                      onClick={() => setAnalysisOffset(Math.max(0, analysisOffset - 100))}
                    >
                      前へ
                    </button>
                    <span>{analysisOffset + 1}件目から</span>
                    <button
                      className="button secondary"
                      disabled={!analysis.data?.has_more}
                      onClick={() => setAnalysisOffset(analysisOffset + 100)}
                    >
                      次へ
                    </button>
                  </div>
                )}
                {analysis.isError && <p className="error-message">{analysis.error.message}</p>}
                {cells.isError && <p className="error-message">{cells.error.message}</p>}
              </div>
            </div>
            <aside className="detail-aside">
              <CoverPicker media={m} onChanged={refresh} />
              <div className="section-heading">
                <h3>動画について</h3>
                <button
                  className="icon-button"
                  aria-label="動画の情報を編集"
                  onClick={() => setMetadata(true)}
                >
                  <Pencil size={16} />
                </button>
              </div>
              <p className="detail-note">{m.note || 'メモを追加して、あとで見つけやすく。'}</p>
              <div className="tags">
                {m.tags.map((t) => (
                  <span key={t}>#{t}</span>
                ))}
              </div>
              <div className="aside-actions">
                <button
                  onClick={() =>
                    act(() =>
                      api('/media/' + id, {
                        method: 'PATCH',
                        body: JSON.stringify({ favorite: !m.favorite }),
                      }),
                    )
                  }
                >
                  <Heart size={17} fill={m.favorite ? 'currentColor' : 'none'} />
                  {m.favorite ? 'お気に入りから外す' : 'お気に入りに追加'}
                </button>
                <button onClick={() => onOrganize(m)}>
                  <FolderPlus size={17} />
                  整理する
                </button>
                {m.assets.original && (
                  <a href={m.assets.original + '?download=true'} download={m.original_filename}>
                    <Download size={17} />
                    元の動画をダウンロード
                  </a>
                )}
                <button className="danger-text" onClick={() => setDeleting(m)}>
                  <Trash2 size={17} />
                  動画を削除
                </button>
              </div>
              <div className="provenance">
                <Info size={16} />
                <p>Cellは元の動画を参照します。動画ファイルの複製は作りません。</p>
              </div>
            </aside>
          </div>
          {error && !editor && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <Modal
            open={!!editor}
            onClose={() => setEditor(null)}
            className="trim-editor"
            title={editor?.cell ? 'Cellを編集' : '動画を切り取る'}
            actions={
              <button
                type="submit"
                form={`cell-editor-${id}`}
                className="button primary compact"
                disabled={busy}
              >
                <Check size={16} />
                {busy ? '保存中…' : 'Cellを保存'}
              </button>
            }
          >
            <form id={`cell-editor-${id}`} onSubmit={form.handleSubmit(saveCell)} className="form">
              <video
                ref={rangeVideo}
                className="range-video"
                src={m.assets.preview}
                controls
                playsInline
                preload="auto"
                onLoadedMetadata={() => {
                  if (rangeVideo.current) rangeVideo.current.currentTime = watched.start;
                }}
                onTimeUpdate={() => {
                  const el = rangeVideo.current;
                  if (el) {
                    setTrimPosition(el.currentTime);
                    if (el.currentTime >= watched.end) el.pause();
                  }
                }}
              />
              <TrimTimeline
                source={m.assets.preview}
                cover={m.assets.thumbnail}
                duration={m.duration_ms / 1000}
                start={watched.start}
                end={watched.end}
                position={trimPosition}
                disabled={busy}
                onChange={(start, end, seek) => {
                  form.setValue('start', start);
                  form.setValue('end', end);
                  if (rangeVideo.current && seek !== undefined) {
                    rangeVideo.current.pause();
                    rangeVideo.current.currentTime = seek === end ? Math.max(start, end - 0.001) : seek;
                  }
                }}
              />
              <label>
                タイトル
                <input {...form.register('title')} placeholder="どんな瞬間ですか？" maxLength={200} />
              </label>
              {form.formState.errors.title && (
                <p className="error-message">{form.formState.errors.title.message}</p>
              )}
              <details className="trim-precision">
                <summary>時刻を細かく指定</summary>
                <div className="form-grid">
                  <label>
                    開始（秒）
                    <input
                      type="number"
                      min={0}
                      max={m.duration_ms / 1000}
                      step="0.001"
                      {...form.register('start', { valueAsNumber: true })}
                    />
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        form.setValue(
                          'start',
                          Math.round((rangeVideo.current?.currentTime ?? position) * 1000) / 1000,
                        )
                      }
                    >
                      現在の位置を使う
                    </button>
                  </label>
                  <label>
                    終了（秒）
                    <input
                      type="number"
                      min={0}
                      max={m.duration_ms / 1000}
                      step="0.001"
                      {...form.register('end', { valueAsNumber: true })}
                    />
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        form.setValue(
                          'end',
                          Math.round((rangeVideo.current?.currentTime ?? position) * 1000) / 1000,
                        )
                      }
                    >
                      現在の位置を使う
                    </button>
                  </label>
                </div>
              </details>
              {form.formState.errors.end && (
                <p className="error-message">{form.formState.errors.end.message}</p>
              )}
              <details className="trim-precision trim-metadata">
                <summary>メモ・タグを追加</summary>
                <div className="form">
                  <label>
                    メモ
                    <textarea {...form.register('note')} rows={2} placeholder="覚えておきたいこと" />
                  </label>
                  <label>
                    タグ
                    <input {...form.register('tags')} placeholder="旅行, お気に入り（カンマで区切る）" />
                  </label>
                </div>
              </details>
              {error && (
                <p className="error-message" role="alert">
                  {error}
                </p>
              )}
              <div className="form-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => {
                    const el = rangeVideo.current;
                    if (el) {
                      el.currentTime = watched.start;
                      void el.play().catch(() => {});
                    }
                  }}
                >
                  <Play size={15} />
                  区間を試聴
                </button>
              </div>
            </form>
          </Modal>
          <Modal open={metadata} onClose={() => setMetadata(false)} title="動画の情報を編集">
            <form
              className="form"
              onSubmit={async (e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                if (
                  await act(
                    () =>
                      api('/media/' + id, {
                        method: 'PATCH',
                        body: JSON.stringify({
                          title: data.get('title'),
                          note: data.get('note'),
                          tags: splitTags(String(data.get('tags'))),
                        }),
                      }),
                    '動画の情報を保存しました',
                  )
                )
                  setMetadata(false);
              }}
            >
              <label>
                タイトル
                <input name="title" defaultValue={m.title} required maxLength={200} />
              </label>
              <label>
                メモ
                <textarea name="note" defaultValue={m.note} rows={4} maxLength={10000} />
              </label>
              <label>
                タグ
                <input name="tags" defaultValue={m.tags.join(', ')} placeholder="カンマで区切って入力" />
              </label>
              {error && <p className="error-message">{error}</p>}
              <div className="form-actions">
                <button className="button primary" disabled={busy}>
                  変更を保存
                </button>
              </div>
            </form>
          </Modal>
          <Confirm
            open={!!runDeleting}
            onClose={() => setRunDeleting(null)}
            title="解析履歴を削除しますか？"
            description="この解析の候補を削除します。自分で保存したCellは残ります。"
            pending={busy}
            onConfirm={async () => {
              if (
                runDeleting &&
                (await act(
                  () => api(`/media/${id}/analysis/${runDeleting}`, { method: 'DELETE' }),
                  '解析履歴を削除しました',
                ))
              )
                setRunDeleting(null);
            }}
          />
          <Confirm
            open={!!deleting}
            onClose={() => setDeleting(null)}
            title={deleting && 'media_id' in deleting ? 'Cellを削除しますか？' : '動画を削除しますか？'}
            description={
              deleting && 'media_id' in deleting
                ? 'このCellだけを削除します。元の動画は残ります。'
                : '元の動画、再生用ファイル、すべてのCellと解析結果が削除されます。この操作は取り消せません。'
            }
            pending={busy}
            onConfirm={async () => {
              if (!deleting) return;
              const isCell = 'media_id' in deleting;
              if (
                await act(
                  () => api((isCell ? '/cells/' : '/media/') + deleting.id, { method: 'DELETE' }),
                  '削除しました',
                )
              ) {
                setDeleting(null);
                if (!isCell) onClose();
              }
            }}
          />
        </>
      )}
    </Modal>
  );
}

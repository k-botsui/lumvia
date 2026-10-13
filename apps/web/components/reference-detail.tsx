'use client';
import { useUploadLimits } from '@/lib/upload-limits';
import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Play, Heart, Pencil, FolderPlus, Trash2, Link2, UploadCloud } from 'lucide-react';
import { api, Cell, Media } from '@/lib/api';
import { Modal } from './ui/dialog';
import { Confirm } from './ui/confirm';
import { CoverPicker } from './cover-picker';
import { ReferenceCells, LinkRange } from './reference-cells';
import { ReferenceVideoPlayer, ReferenceVideoHandle, ReferencePlayback } from './reference-video-player';
import { PublicPreviewPlayer, usePublicPreview } from './public-preview';

function embedUrl(media: Media, initialTime: number, end?: number, autoplay = false) {
  const source = media.source,
    id = encodeURIComponent(source.external_id || '');
  switch (source.provider) {
    case 'youtube': {
      const start = Number.isFinite(initialTime) && initialTime > 0 ? initialTime : source.start_ms;
      return `https://www.youtube-nocookie.com/embed/${id}?playsinline=1&start=${Math.floor(Math.max(0, Math.min(start, 86400000)) / 1000)}${end !== undefined ? `&end=${Math.ceil(end / 1000)}` : ''}&autoplay=${autoplay ? 1 : 0}`;
    }
    case 'x':
      return `https://platform.twitter.com/embed/Tweet.html?id=${id}&dnt=true&lang=ja&theme=light`;
    case 'instagram':
      return source.url ? `${source.url}embed/` : '';
    case 'tiktok':
      return `https://www.tiktok.com/player/v1/${id}?autoplay=${autoplay ? 1 : 0}&description=1&music_info=1`;
    default:
      return '';
  }
}

export function ReferenceDetail({
  media: m,
  initialTime,
  initialEnd,
  onClose,
  onChanged,
  notify,
  onOrganize,
  onOpenCell,
}: {
  media: Media;
  initialTime: number;
  initialEnd?: number;
  onClose: () => void;
  onChanged: () => void;
  notify: (s: string) => void;
  onOrganize: (m: Media | Cell) => void;
  onOpenCell: (cell: Cell) => void;
}) {
  const uploadLimits = useUploadLimits();
  const [showPlayer, setShowPlayer] = useState(false),
    [editing, setEditing] = useState(false),
    [deleting, setDeleting] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const videoPlayer = useRef<ReferenceVideoHandle>(null);
  const playerPanel = useRef<HTMLDivElement>(null);
  const pendingPlayback = useRef<ReferencePlayback | null>(null);
  const [trimming, setTrimming] = useState(false);
  const [position, setPosition] = useState(0);
  const [actualDuration, setActualDuration] = useState<number>();
  const publicPreview = usePublicPreview(m.id, trimming);
  const previewPlayer = useRef<ReferenceVideoHandle>(null);
  const playable = !!publicPreview.data || ['youtube', 'tiktok'].includes(m.source.provider);
  const src = embedUrl(m, initialTime);
  function playback(request: ReferencePlayback) {
    if (trimming && previewPlayer.current) previewPlayer.current.show(request);
    else if (videoPlayer.current) videoPlayer.current.show(request);
    else pendingPlayback.current = request;
    setShowPlayer(true);
  }
  function preview(range: LinkRange) {
    playback({ start: range.start, end: range.end, play: true });
  }
  useEffect(() => {
    if (showPlayer && pendingPlayback.current && videoPlayer.current) {
      videoPlayer.current.show(pendingPlayback.current);
      pendingPlayback.current = null;
    }
  }, [showPlayer]);
  useEffect(() => {
    if (trimming) playerPanel.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [trimming]);
  async function attach(file?: File) {
    if (!file || busy) return;
    if (file.size > uploadLimits.max_upload_bytes || !/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(file.name)) {
      setError(
        `${Math.round(uploadLimits.max_upload_bytes / 1024 ** 2)} MB以下のMOV・MP4などの動画ファイルを選んでください。`,
      );
      return;
    }
    const body = new FormData();
    body.append('file', file);
    body.append('reference_id', m.id);
    await act(
      () => api('/media', { method: 'POST', body, headers: { 'Idempotency-Key': crypto.randomUUID() } }),
      '元動画を追加しました。再生の準備をしています',
    );
  }
  const start = Number.isFinite(initialTime) && initialTime > 0 ? initialTime : m.source.start_ms;
  const originalUrl =
    m.source.url && m.source.provider === 'youtube' && start > 0
      ? `${m.source.url}&t=${Math.floor(Math.min(start, 86400000) / 1000)}s`
      : m.source.url;
  async function act(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError('');
    try {
      await action();
      onChanged();
      notify(message);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title={m.title} wide description={`${m.source.label}から保存したリンク`}>
      <div className={`detail-columns ${trimming ? 'reference-editing' : ''}`}>
        <div className="detail-main">
          <div
            ref={playerPanel}
            className={`reference-player ${m.source.provider} ${showPlayer ? 'loaded' : ''}`}
          >
            {trimming && publicPreview.data ? (
              <PublicPreviewPlayer
                ref={previewPlayer}
                source={publicPreview.data.url}
                initialTime={initialTime || m.source.start_ms}
                onTime={(at, duration) => {
                  setPosition(at);
                  setActualDuration(duration);
                }}
              />
            ) : showPlayer && ['youtube', 'tiktok'].includes(m.source.provider) ? (
              <ReferenceVideoPlayer
                ref={videoPlayer}
                media={m}
                initialTime={initialTime || m.source.start_ms}
                initialEnd={initialEnd}
                onTime={(at, duration) => {
                  setPosition(at);
                  setActualDuration(duration);
                }}
              />
            ) : showPlayer && src ? (
              <iframe
                src={src}
                title={`${m.source.label} · ${m.title}`}
                allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
                sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation"
              />
            ) : (
              <div className="reference-placeholder">
                {m.assets.thumbnail || m.source.thumbnail_url ? (
                  <img
                    className="reference-cover"
                    src={m.assets.thumbnail || m.source.thumbnail_url!}
                    alt=""
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <Link2 size={34} />
                )}
                <h3>{m.source.label}の動画・投稿</h3>
                <p>プレーヤーを表示すると{m.source.label}へ接続します。</p>
                <button className="button primary" onClick={() => setShowPlayer(true)}>
                  <Play size={17} />
                  プレーヤーを表示
                </button>
              </div>
            )}
          </div>
          {trimming && playable && (
            <div className="scene-preview-status">
              <output aria-label="確認中の再生位置">{position.toFixed(1)}秒の場面</output>
              <button
                type="button"
                className="text-button"
                onClick={() => playback({ start: 0, play: true })}
              >
                動画全体を再生
              </button>
            </div>
          )}
          <div className="reference-info">
            <div className="reference-actions">
              <span className="badge">リンク保存 · {m.source.label}</span>
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
            <p className="reference-help">
              再生できない、ログインが必要、または投稿が表示されない場合は「{m.source.label}
              で開く」を使ってください。
              {m.source.provider === 'instagram' && 'InstagramのログインはInstagramの画面で行えます。'}
              {m.source.provider === 'tiktok' &&
                '初回に再生が始まらないときは、プレーヤー内の再生ボタンを押してください。'}
            </p>
            {m.source.author && <p className="muted">投稿者：{m.source.author}</p>}
            <CoverPicker media={m} onChanged={onChanged} />
            <p className="source-link">{m.source.url}</p>
          </div>
          <ReferenceCells
            media={m}
            initialTime={initialTime || m.source.start_ms}
            initialEnd={initialEnd}
            actualDuration={publicPreview.data ? publicPreview.data.duration_ms / 1000 : actualDuration}
            previewSource={publicPreview.data?.url}
            previewLoading={publicPreview.isFetching}
            previewError={publicPreview.isError ? publicPreview.error.message : ''}
            onRetryPreview={() => void publicPreview.refetch()}
            position={position}
            onPreview={preview}
            onInspect={(at) => playback({ start: at, play: !publicPreview.data })}
            onEditing={(active) => {
              setTrimming(active);
              if (!active) {
                videoPlayer.current?.show({ play: false });
                previewPlayer.current?.show({ play: false });
              } else if (playable) playback({ play: false });
            }}
            onChanged={onChanged}
            onOrganize={onOrganize}
            onOpenCell={onOpenCell}
            notify={notify}
          />
          <div className="reference-file">
            <div>
              <h3>元動画ファイルを追加</h3>
              <p>区間のサムネイル・MP4書き出しを使えます。保存したCellとメモは引き継ぎます。</p>
            </div>
            <button className="button secondary" disabled={busy} onClick={() => fileInput.current?.click()}>
              <UploadCloud size={16} />
              {busy ? '追加しています…' : '動画ファイルを選ぶ'}
            </button>
            <input
              ref={fileInput}
              type="file"
              hidden
              accept=".mp4,.mov,.m4v,.webm,.mkv,.avi"
              onChange={(e) => {
                void attach(e.target.files?.[0]);
                e.target.value = '';
              }}
            />
          </div>
        </div>
        <aside className="detail-aside">
          <h3>メモ</h3>
          <p className="detail-note">{m.note || '覚えておきたいことを、メモに残せます。'}</p>
          <div className="tags">
            {m.tags.map((t) => (
              <span key={t}>#{t}</span>
            ))}
          </div>
          <div className="aside-actions">
            <button
              disabled={busy}
              onClick={() =>
                void act(
                  () =>
                    api('/media/' + m.id, {
                      method: 'PATCH',
                      body: JSON.stringify({ favorite: !m.favorite }),
                    }),
                  'お気に入りを更新しました',
                )
              }
              aria-pressed={m.favorite}
            >
              <Heart size={16} fill={m.favorite ? 'currentColor' : 'none'} />
              {m.favorite ? 'お気に入りを解除' : 'お気に入りに追加'}
            </button>
            <button onClick={() => onOrganize(m)}>
              <FolderPlus size={16} />
              Shelfに整理
            </button>
            <button onClick={() => setEditing(true)}>
              <Pencil size={16} />
              タイトル・メモ・タグを編集
            </button>
            <button onClick={() => setDeleting(true)}>
              <Trash2 size={16} />
              リンクを削除
            </button>
          </div>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
        </aside>
      </div>
      <Modal open={editing} onClose={() => setEditing(false)} title="リンクの情報を編集">
        <form
          className="form"
          onSubmit={async (e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            const tags = [
              ...new Set(
                String(data.get('tags'))
                  .split(/[,、]/)
                  .map((s) => s.trim())
                  .filter(Boolean),
              ),
            ].slice(0, 20);
            if (
              await act(
                () =>
                  api('/media/' + m.id, {
                    method: 'PATCH',
                    body: JSON.stringify({ title: data.get('title'), note: data.get('note'), tags }),
                  }),
                'リンクの情報を保存しました',
              )
            )
              setEditing(false);
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
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <button className="button primary" disabled={busy}>
              変更を保存
            </button>
          </div>
        </form>
      </Modal>
      <Confirm
        open={deleting}
        onClose={() => setDeleting(false)}
        title="リンクを削除しますか？"
        description="Lumviaに保存したリンク・Cell・メモ・整理先を削除します。元のサービスの投稿は残ります。"
        pending={busy}
        onConfirm={async () => {
          if (await act(() => api('/media/' + m.id, { method: 'DELETE' }), 'リンクを削除しました')) onClose();
        }}
      />
    </Modal>
  );
}

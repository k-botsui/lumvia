'use client';
import { useEffect, useRef, useState } from 'react';
import { animate, motion, useInView, useMotionValue, useReducedMotion } from 'motion/react';
import { ChevronLeft, ChevronRight, Film, Pause, Play, Plus } from 'lucide-react';
import { Media, time } from '@/lib/api';

const spring = { type: 'spring' as const, stiffness: 300, damping: 32, mass: 0.85 };

function SpatialGallery({
  items,
  onOpen,
  active = true,
}: {
  items: Media[];
  onOpen: (id: string) => void;
  active?: boolean;
}) {
  const reduced = useReducedMotion();
  const host = useRef<HTMLDivElement>(null);
  const inView = useInView(host, { amount: 0.35 });
  const [width, setWidth] = useState(900);
  const [selected, setSelected] = useState(0);
  const [enabled, setEnabled] = useState(true);
  const [visible, setVisible] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [failed, setFailed] = useState('');
  const [failedCover, setFailedCover] = useState('');
  const dragX = useMotionValue(0);
  const dragAnimation = useRef<ReturnType<typeof animate> | null>(null);
  const dragged = useRef(false);
  const videos = items.slice(0, 7);
  const index = Math.min(selected, videos.length - 1);
  const current = videos[index];
  const cardWidth = Math.min(640, width < 600 ? width * 0.85 : width * 0.72);
  const cardHeight = (cardWidth * 9) / 16;
  const playback = active && enabled && !reduced && inView && visible && !dragging;
  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  }, []);
  useEffect(() => () => dragAnimation.current?.stop(), []);
  function choose(next: number, focus = false) {
    setSelected((next + videos.length) % videos.length);
    if (focus)
      requestAnimationFrame(() =>
        host.current?.querySelector<HTMLButtonElement>('[role="tab"][aria-selected="true"]')?.focus(),
      );
  }
  function offset(i: number) {
    let d = i - index;
    const half = videos.length / 2;
    if (d > half) d -= videos.length;
    if (d < -half) d += videos.length;
    return d;
  }
  return (
    <div className="spatial-gallery" ref={host}>
      <div className="gallery-heading">
        <h2>最近追加した動画</h2>
        <span>
          {String(index + 1).padStart(2, '0')}
          <i>/ {String(videos.length).padStart(2, '0')}</i>
        </span>
      </div>
      <div
        className="gallery-stage"
        style={{ height: cardHeight + 30 }}
        role="tabpanel"
        id="gallery-selected-video"
        aria-labelledby={`gallery-tab-${current.id}`}
      >
        <motion.div
          className="gallery-track"
          style={{ x: dragX }}
          drag={reduced ? false : 'x'}
          dragMomentum={false}
          onDragStart={() => {
            dragAnimation.current?.stop();
            dragged.current = true;
            setDragging(true);
          }}
          onDragEnd={(_, info) => {
            setDragging(false);
            const projected = info.offset.x + info.velocity.x * 0.16;
            if (Math.abs(projected) > cardWidth * 0.14) choose(index + (projected < 0 ? 1 : -1), true);
            dragAnimation.current = animate(dragX, 0, { ...spring, velocity: info.velocity.x });
            requestAnimationFrame(() => {
              dragged.current = false;
            });
          }}
        >
          {videos.map((media, i) => {
            const distance = offset(i),
              active = distance === 0;
            const cover = media.assets.thumbnail || media.source.thumbnail_url;
            return (
              <motion.article
                key={media.id}
                className={`gallery-card ${active ? 'is-current' : ''}`}
                data-media-surface={media.id}
                initial={false}
                animate={{
                  x: distance * cardWidth * 0.84,
                  y: active ? 0 : 14,
                  scale: active ? 1 : 0.87,
                  rotateY: reduced ? 0 : distance === 0 ? 0 : distance > 0 ? -12 : 12,
                  opacity: Math.abs(distance) > 1 ? 0.15 : active ? 1 : 0.62,
                }}
                transition={reduced ? { duration: 0.1 } : spring}
                style={{
                  width: cardWidth,
                  height: cardHeight,
                  zIndex: 20 - Math.abs(distance),
                  pointerEvents: Math.abs(distance) > 1 ? 'none' : 'auto',
                }}
                aria-hidden={!active}
              >
                {cover && failedCover !== cover ? (
                  <img
                    className="gallery-cover"
                    src={cover}
                    alt=""
                    draggable={false}
                    referrerPolicy="no-referrer"
                    onError={() => setFailedCover(cover)}
                  />
                ) : (
                  <div className="gallery-fallback">
                    <Film size={45} />
                  </div>
                )}
                {active && playback && media.assets.preview && failed !== media.id && (
                  <motion.video
                    key={'video-' + media.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.4 }}
                    className="gallery-video"
                    src={media.assets.preview}
                    poster={cover || undefined}
                    muted
                    loop
                    autoPlay
                    playsInline
                    preload="metadata"
                    aria-hidden="true"
                    onError={() => setFailed(media.id)}
                  />
                )}
                <button
                  className="gallery-card-open"
                  tabIndex={active ? 0 : -1}
                  aria-label={active ? `${media.title}を開く` : `${media.title}を選択`}
                  onClick={() => {
                    if (dragged.current) return;
                    if (active) onOpen(media.id);
                    else choose(i, true);
                  }}
                >
                  <span className="gallery-play">
                    <Play size={22} fill="currentColor" />
                  </span>
                </button>
                {active && (
                  <div className="gallery-caption">
                    <div>
                      <h3>{media.title}</h3>
                      <p>
                        {media.source.label}
                        <span>·</span>
                        {media.storage_mode === 'REFERENCE' ? 'リンク保存' : time(media.duration_ms)}
                        <span>·</span>
                        {media.cell_count} Cells
                      </p>
                    </div>
                    <button className="glass-open" onClick={() => onOpen(media.id)} aria-label="動画を開く">
                      <Play size={15} fill="currentColor" />
                      開く
                    </button>
                  </div>
                )}
              </motion.article>
            );
          })}
        </motion.div>
      </div>
      <div className="gallery-control-row">
        <div className="gallery-dock">
          <button
            className="gallery-arrow"
            aria-label="前の動画"
            disabled={videos.length < 2}
            onClick={() => choose(index - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <div className="gallery-thumbnails" role="tablist" aria-label="動画を選択">
            {videos.map((m, i) => (
              <button
                key={m.id}
                className={i === index ? 'selected' : ''}
                aria-label={`${m.title}をプレビュー`}
                role="tab"
                id={`gallery-tab-${m.id}`}
                aria-selected={i === index}
                aria-controls="gallery-selected-video"
                tabIndex={i === index ? 0 : -1}
                onKeyDown={(event) => {
                  if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                    event.preventDefault();
                    const next = (i + (event.key === 'ArrowRight' ? 1 : -1) + videos.length) % videos.length;
                    choose(next);
                    event.currentTarget.parentElement
                      ?.querySelectorAll<HTMLButtonElement>('[role=tab]')
                      [next]?.focus();
                  }
                }}
                onClick={() => choose(i)}
              >
                {i === index && (
                  <motion.span
                    className="thumbnail-selection"
                    layoutId="gallery-selection"
                    transition={reduced ? { duration: 0 } : spring}
                  />
                )}
                {m.assets.thumbnail || m.source.thumbnail_url ? (
                  <img
                    src={m.assets.thumbnail || m.source.thumbnail_url!}
                    alt=""
                    draggable={false}
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <Film size={15} />
                )}
              </button>
            ))}
          </div>
          <button
            className="gallery-arrow"
            aria-label="次の動画"
            disabled={videos.length < 2}
            onClick={() => choose(index + 1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
        {current.assets.preview && !reduced && (
          <button
            className="preview-toggle"
            onClick={() => setEnabled(!enabled)}
            aria-pressed={enabled}
            aria-label={enabled ? 'プレビューを一時停止' : 'プレビューを再生'}
          >
            {enabled ? <Pause size={13} /> : <Play size={13} />}
            <span>{enabled ? '一時停止' : 'プレビュー'}</span>
          </button>
        )}
      </div>
    </div>
  );
}

export function LibraryWelcome({
  items,
  counts,
  onOpen,
  onNavigate,
  loading = false,
  error,
  onRetry,
  previewActive = true,
}: {
  items: Media[];
  counts: { videos?: number; cells?: number; shelves?: number };
  onOpen: (id: string) => void;
  onNavigate: (values: Record<string, string>) => void;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  previewActive?: boolean;
}) {
  return (
    <section className="library-welcome" aria-label="ホーム">
      <div className="welcome-heading">
        <div>
          <h1>ホーム</h1>
          <p className="welcome-description">
            {counts.videos ?? '—'}本の動画<span>·</span>
            {counts.cells ?? '—'} Cells<span>·</span>
            {counts.shelves ?? '—'} Shelves
          </p>
        </div>
        <button className="button primary" onClick={() => onNavigate({ view: 'add' })}>
          <Plus size={17} />
          追加する
        </button>
      </div>
      {loading ? (
        <div className="home-loading" role="status" aria-label="動画を読み込み中">
          <div className="skeleton" />
        </div>
      ) : error ? (
        <div className="home-load-error" role="alert">
          <h2>動画を読み込めませんでした</h2>
          <p>{error}</p>
          <button className="button secondary" onClick={onRetry}>
            再試行
          </button>
        </div>
      ) : items.length ? (
        <SpatialGallery items={items} onOpen={onOpen} active={previewActive} />
      ) : (
        <div className="home-empty">
          <Film size={34} />
          <h2>動画がありません</h2>
          <p>動画ファイルまたはリンクを追加してください。</p>
          <button className="button primary" onClick={() => onNavigate({ view: 'add' })}>
            動画を追加
          </button>
        </div>
      )}
      {!!items.length && (
        <button className="gallery-library-link" onClick={() => onNavigate({ view: 'library' })}>
          ライブラリを表示
          <ChevronRight size={14} />
        </button>
      )}
    </section>
  );
}

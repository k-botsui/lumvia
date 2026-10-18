'use client';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { Heart, Play, Layers, Film, Loader2, AlertCircle } from 'lucide-react';
import { Media, time, date } from '@/lib/api';
export function MediaCard({
  media,
  onOpen,
  onFavorite,
  selecting = false,
  selected = false,
  onSelect,
  onContextMenu,
}: {
  media: Media;
  onOpen: () => void;
  onFavorite: () => void;
  selecting?: boolean;
  selected?: boolean;
  onSelect?: (shift?: boolean) => void;
  onContextMenu?: (event: React.MouseEvent) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(true);
  useEffect(() => {
    const query = matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduceMotion(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return (
    <motion.article
      data-media-surface={media.id}
      className={`media-card ${selected && selecting ? 'item-selected' : ''}`}
      whileHover={{ y: -5 }}
      whileTap={{ scale: 0.985 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
    >
      <div
        className="thumbnail"
        onPointerEnter={(event) => {
          if (event.pointerType === 'mouse' && !reduceMotion && !selecting) setHovered(true);
        }}
        onPointerLeave={() => {
          setHovered(false);
          setPlaying(false);
        }}
      >
        <button
          className="thumbnail-open"
          onContextMenu={onContextMenu}
          onClick={(e) => (selecting ? onSelect?.(e.shiftKey) : onOpen())}
          aria-label={`${media.title}${selecting ? 'を選択' : 'を開く'}`}
          aria-pressed={selecting ? selected : undefined}
        >
          {media.assets.thumbnail || media.source.thumbnail_url ? (
            <img
              src={media.assets.thumbnail || media.source.thumbnail_url!}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="thumbnail-placeholder">
              {media.status === 'PROCESSING' ? (
                <Loader2 className="spin" size={32} />
              ) : media.status === 'FAILED' ? (
                <AlertCircle size={32} />
              ) : media.storage_mode === 'REFERENCE' ? (
                <div className={`reference-card-cover ${media.source.provider}`}>
                  <small>
                    {media.source.label}
                    {media.source.author && ` · ${media.source.author}`}
                  </small>
                  <strong>{media.title}</strong>
                  <span>カバー画像を設定できます</span>
                </div>
              ) : (
                <Film size={32} />
              )}
            </div>
          )}
          {hovered && !reduceMotion && media.assets.preview && (
            <video
              className={`card-motion-preview ${playing ? 'is-playing' : ''}`}
              src={media.assets.preview}
              muted
              loop
              playsInline
              autoPlay
              preload="none"
              aria-hidden="true"
              onPlaying={() => setPlaying(true)}
              onError={() => setPlaying(false)}
            />
          )}
          {!selecting && (
            <span className="play-overlay">
              <Play size={23} fill="currentColor" />
            </span>
          )}
        </button>
        <button
          className={`favorite-button ${media.favorite ? 'selected' : ''}`}
          onClick={onFavorite}
          aria-label={media.favorite ? 'お気に入りを解除' : 'お気に入りに追加'}
          aria-pressed={media.favorite}
        >
          <Heart size={17} fill={media.favorite ? 'currentColor' : 'none'} />
        </button>
        <span className="duration">
          {media.storage_mode === 'REFERENCE'
            ? media.source.label
            : media.status === 'READY'
              ? time(media.duration_ms)
              : media.status === 'PROCESSING'
                ? '準備中'
                : '確認が必要'}
        </span>
      </div>
      {selecting && (
        <label className="item-select">
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => onSelect?.((e.nativeEvent as MouseEvent).shiftKey)}
            aria-label={media.title + 'を選択'}
          />
        </label>
      )}
      <button
        onContextMenu={onContextMenu}
        className="card-title"
        onClick={(e) => (selecting ? onSelect?.(e.shiftKey) : onOpen())}
      >
        {media.title}
      </button>
      <div className="card-meta">
        <span>{date(media.created_at)}</span>
        <span>
          {media.storage_mode === 'REFERENCE' ? (
            'リンク保存'
          ) : (
            <>
              <Layers size={13} />
              {media.cell_count} Cells
            </>
          )}
        </span>
      </div>
      {media.tags.length > 0 && (
        <div className="tags">
          {media.tags.slice(0, 3).map((t) => (
            <span key={t}>#{t}</span>
          ))}
        </div>
      )}
    </motion.article>
  );
}

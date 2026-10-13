'use client';
import { useRef, useState } from 'react';
import { api, Media, time } from '@/lib/api';
import { Modal } from './ui/dialog';

export function VideoCoverPicker({
  media,
  onClose,
  onChanged,
}: {
  media: Media;
  onClose: () => void;
  onChanged: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [position, setPosition] = useState(0);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save() {
    const el = video.current;
    if (!el || !ready || !el.videoWidth) return;
    setBusy(true);
    setError('');
    try {
      el.pause();
      await api(`/media/${media.id}/frame-cover`, {
        method: 'POST',
        body: JSON.stringify({ position_ms: Math.round(position * 1000) }),
      });
      onChanged();
      onClose();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      title="動画からカバーを選ぶ"
      description="スライダーで好きな場面を選び、画像として保存します。動画本体は変更しません。"
    >
      <div className="video-frame">
        <video
          ref={video}
          src={media.assets.preview}
          playsInline
          preload="auto"
          onLoadedMetadata={(event) => {
            const el = event.currentTarget;
            el.currentTime = Math.min(el.duration / 3, 10);
            setPosition(el.currentTime);
          }}
          onLoadedData={() => setReady(true)}
          onSeeking={() => setReady(false)}
          onSeeked={() => setReady(true)}
          onError={() => setError('動画を読み込めませんでした。閉じてもう一度お試しください。')}
        />
      </div>
      <label className="form">
        場面：{time(Math.round(position * 1000))}
        <input
          type="range"
          min="0"
          max={Math.max(0, media.duration_ms / 1000 - 0.05)}
          step="0.05"
          value={position}
          disabled={busy}
          aria-label="カバーに使う場面"
          onChange={(event) => {
            const value = Number(event.target.value);
            setPosition(value);
            setReady(false);
            if (video.current) video.current.currentTime = value;
          }}
        />
      </label>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="modal-actions">
        <button className="button primary" disabled={!ready || busy} onClick={() => void save()}>
          {busy ? '保存中…' : 'この場面をカバーにする'}
        </button>
      </div>
    </Modal>
  );
}

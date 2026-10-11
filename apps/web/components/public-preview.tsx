'use client';
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ReferenceVideoHandle, ReferencePlayback } from './reference-video-player';

export type PublicPreview = {
  url: string;
  duration_ms: number;
  width: number;
  height: number;
  expires_at: number;
};

export function usePublicPreview(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ['public-preview', id],
    queryFn: ({ signal }) => api<PublicPreview>(`/media/${id}/reference-preview`, { method: 'POST', signal }),
    enabled,
    staleTime: 25 * 60 * 1000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export const PublicPreviewPlayer = forwardRef<
  ReferenceVideoHandle,
  {
    source: string;
    initialTime: number;
    onTime: (position: number, duration: number) => void;
  }
>(({ source, initialTime, onTime }, ref) => {
  const video = useRef<HTMLVideoElement>(null);
  const request = useRef<ReferencePlayback>({ start: initialTime / 1000, play: false });
  const stopAt = useRef<number | undefined>(undefined);
  const callback = useRef(onTime);
  useEffect(() => {
    callback.current = onTime;
  }, [onTime]);
  function apply(next: ReferencePlayback) {
    request.current = next;
    const el = video.current;
    if (!el || el.readyState < 1) return;
    stopAt.current = next.end;
    if (next.start !== undefined) el.currentTime = Math.max(0, Math.min(el.duration - 0.001, next.start));
    if (next.play) void el.play().catch(() => {});
    else el.pause();
  }
  useImperativeHandle(ref, () => ({ show: apply }), []);
  useEffect(() => {
    const el = video.current;
    if (!el) return;
    let frame = 0;
    const update = () => {
      if (stopAt.current !== undefined && el.currentTime >= stopAt.current) {
        el.pause();
        el.currentTime = Math.max(0, stopAt.current - 0.001);
        stopAt.current = undefined;
      }
      if (Number.isFinite(el.duration)) callback.current(el.currentTime, el.duration);
    };
    const tick = () => {
      update();
      if (!el.paused) frame = requestAnimationFrame(tick);
    };
    const start = () => {
      cancelAnimationFrame(frame);
      tick();
    };
    el.addEventListener('play', start);
    el.addEventListener('timeupdate', update);
    el.addEventListener('seeked', update);
    return () => {
      el.pause();
      cancelAnimationFrame(frame);
      el.removeEventListener('play', start);
      el.removeEventListener('timeupdate', update);
      el.removeEventListener('seeked', update);
    };
  }, [source]);
  return (
    <video
      ref={video}
      src={source}
      controls
      playsInline
      preload="metadata"
      aria-label="一時取得した動画のプレビュー"
      onLoadedMetadata={() => {
        apply(request.current);
        const el = video.current!;
        callback.current(el.currentTime, el.duration);
      }}
    />
  );
});
PublicPreviewPlayer.displayName = 'PublicPreviewPlayer';

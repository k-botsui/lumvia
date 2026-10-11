'use client';
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { time } from '@/lib/api';

export function TrimTimeline({
  source,
  cover,
  duration,
  start,
  end,
  position,
  onChange,
  disabled = false,
  livePreview = false,
}: {
  source?: string;
  cover?: string;
  duration: number;
  start: number;
  end: number;
  position?: number;
  onChange: (start: number, end: number, seek?: number) => void;
  disabled?: boolean;
  livePreview?: boolean;
}) {
  const rail = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<'start' | 'end' | null>(null);
  const [windowRange, setWindowRange] = useState<[number, number] | null>(null);
  const left = windowRange?.[0] ?? 0,
    right = windowRange?.[1] ?? duration;
  const minimumSpan = Math.min(0.1, duration);
  const span = Math.max(0.001, right - left);
  const percentage = (value: number) => Math.max(0, Math.min(100, ((value - left) / span) * 100));
  useEffect(() => {
    if (!source || !duration || !canvas.current) return;
    const element = canvas.current,
      context = element.getContext('2d');
    const video = document.createElement('video');
    video.muted = true;
    video.preload = 'metadata';
    let disposed = false;
    const abort = new AbortController();
    const ready = (event: string, action?: () => void) =>
      new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => done(new Error('Frame timeout')), 2500);
        const done = (error?: unknown) => {
          clearTimeout(timeout);
          video.removeEventListener(event, loaded);
          abort.signal.removeEventListener('abort', cancelled);
          if (error) reject(error);
          else resolve();
        };
        const loaded = () => done(),
          cancelled = () => done(new Error('Closed'));
        video.addEventListener(event, loaded, { once: true });
        abort.signal.addEventListener('abort', cancelled, { once: true });
        action?.();
      });
    void (async () => {
      try {
        context?.clearRect(0, 0, 960, 80);
        await ready('loadedmetadata', () => {
          video.src = source;
        });
        for (let index = 0; index < 12 && !disposed; index++) {
          const at = Math.min(
            Math.max(0, video.duration - 0.001),
            Math.max(0.001, left + ((right - left) * (index + 0.5)) / 12),
          );
          await ready('seeked', () => {
            video.currentTime = at;
          });
          if (disposed || !context) break;
          const scale = Math.min(80 / video.videoWidth, 80 / video.videoHeight);
          const w = video.videoWidth * scale,
            h = video.videoHeight * scale;
          context.save();
          context.beginPath();
          context.rect(index * 80, 0, 80, 80);
          context.clip();
          context.fillStyle = '#1d1d1f';
          context.fillRect(index * 80, 0, 80, 80);
          context.drawImage(video, index * 80 + (80 - w) / 2, (80 - h) / 2, w, h);
          context.restore();
        }
      } catch {
        /* A cover remains visible if a browser cannot decode timeline frames. */
      }
    })();
    return () => {
      disposed = true;
      abort.abort();
      video.pause();
      video.removeAttribute('src');
      video.load();
    };
  }, [source, duration, left, right]);
  function change(side: 'start' | 'end', value: number) {
    if (disabled) return;
    const snapped = Math.round(value * 1000) / 1000;
    if (side === 'start') {
      const next = Math.max(0, end - 300, Math.min(end - minimumSpan, snapped));
      onChange(next, end, next);
    } else {
      const next = Math.min(duration, start + 300, Math.max(start + minimumSpan, snapped));
      onChange(start, next, next);
    }
  }
  function move(event: PointerEvent<HTMLButtonElement>) {
    if (!drag.current || !rail.current) return;
    const bounds = rail.current.getBoundingClientRect();
    change(
      drag.current,
      left + Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)) * span,
    );
  }
  function key(event: KeyboardEvent<HTMLButtonElement>, side: 'start' | 'end') {
    const value = side === 'start' ? start : end;
    const step = event.shiftKey ? 1 : 0.1;
    const next =
      event.key === 'ArrowLeft' || event.key === 'ArrowDown'
        ? value - step
        : event.key === 'ArrowRight' || event.key === 'ArrowUp'
          ? value + step
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? duration
              : null;
    if (next !== null) {
      event.preventDefault();
      change(side, next);
    }
  }
  return (
    <div className="trim-timeline">
      <div className="trim-labels">
        <strong>{time(start * 1000, true)}</strong>
        <span>{(end - start).toFixed(1)}秒</span>
        <strong>{time(end * 1000, true)}</strong>
      </div>
      <div
        className={`trim-rail ${!source && !cover ? 'trim-time-rail' : ''}`}
        ref={rail}
        onPointerDown={(e) => {
          if (disabled || !livePreview || (e.target as HTMLElement).closest('button')) return;
          const bounds = e.currentTarget.getBoundingClientRect();
          onChange(
            start,
            end,
            left + Math.max(0, Math.min(1, (e.clientX - bounds.left) / bounds.width)) * span,
          );
        }}
      >
        <div className="trim-frames">
          {Array.from({ length: 12 }, (_, i) =>
            cover ? <img key={i} src={cover} alt="" referrerPolicy="no-referrer" /> : <span key={i} />,
          )}
          <canvas ref={canvas} width={960} height={80} />
        </div>
        <div className="trim-dim left" style={{ width: `${percentage(start)}%` }} />
        <div className="trim-dim right" style={{ width: `${100 - percentage(end)}%` }} />
        <div
          className="trim-selection"
          style={{ left: `${percentage(start)}%`, right: `${100 - percentage(end)}%` }}
        />
        {position !== undefined && position >= left && position <= right && (
          <span className="trim-playhead" style={{ left: `${percentage(position)}%` }} />
        )}
        {(['start', 'end'] as const).map((side) => (
          <button
            key={side}
            type="button"
            role="slider"
            className="trim-handle"
            aria-label={side === 'start' ? '区間の開始' : '区間の終了'}
            aria-valuemin={side === 'start' ? Math.max(0, end - 300) : start + minimumSpan}
            aria-valuemax={side === 'start' ? end - minimumSpan : Math.min(duration, start + 300)}
            aria-valuenow={side === 'start' ? start : end}
            aria-valuetext={time((side === 'start' ? start : end) * 1000, true)}
            disabled={disabled}
            style={{ left: `calc(${percentage(side === 'start' ? start : end)}% - 10px)` }}
            onKeyDown={(e) => key(e, side)}
            onPointerDown={(e) => {
              if (disabled) return;
              drag.current = side;
              e.currentTarget.setPointerCapture(e.pointerId);
            }}
            onPointerMove={move}
            onPointerUp={(e) => {
              drag.current = null;
              e.currentTarget.releasePointerCapture(e.pointerId);
            }}
            onPointerCancel={() => {
              drag.current = null;
            }}
          >
            {side === 'start' ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        ))}
      </div>
      <div className="trim-caption">
        <span>{livePreview ? '両端を動かすと、その場面から再生します' : '両端を動かして区間を選択'}</span>
        {duration > 5 && (
          <button
            type="button"
            className="text-button"
            onClick={() =>
              setWindowRange(windowRange ? null : [Math.max(0, start - 5), Math.min(duration, end + 5)])
            }
          >
            {windowRange ? '全体を見る' : '拡大する'}
          </button>
        )}
      </div>
    </div>
  );
}

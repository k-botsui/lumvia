'use client';
import { useEffect, useRef, useState } from 'react';
import { Maximize, Pause, Play, RotateCcw, Volume2, VolumeX } from 'lucide-react';
import { time } from '@/lib/api';

export function CellControls({
  playing,
  position,
  duration,
  disabled = false,
  onToggle,
  onSeek,
  onRestart,
  onFullscreen,
}: {
  playing: boolean;
  position: number;
  duration: number;
  disabled?: boolean;
  onToggle: () => void;
  onSeek: (seconds: number) => void;
  onRestart: () => void;
  onFullscreen?: () => void;
}) {
  return (
    <div className="cell-controls">
      <button
        className="icon-button"
        disabled={disabled}
        aria-label={playing ? 'Cellを一時停止' : 'Cellを再生'}
        onClick={onToggle}
      >
        {playing ? <Pause size={20} /> : <Play size={20} />}
      </button>
      <button className="icon-button" disabled={disabled} aria-label="Cellを最初から再生" onClick={onRestart}>
        <RotateCcw size={17} />
      </button>
      <input
        type="range"
        aria-label="Cellの再生位置"
        min={0}
        max={duration}
        step={0.01}
        value={Math.max(0, Math.min(duration, position))}
        aria-valuetext={`${time(position * 1000, true)} / ${time(duration * 1000, true)}`}
        disabled={disabled}
        onChange={(e) => onSeek(Number(e.target.value))}
      />
      <output aria-label="Cellの再生時間">
        {time(position * 1000)} / {time(duration * 1000)}
      </output>
      {onFullscreen && (
        <button className="icon-button" aria-label="全画面で表示" onClick={onFullscreen}>
          <Maximize size={17} />
        </button>
      )}
    </div>
  );
}

export function CellPlayer({ src, start, end }: { src: string; start: number; end: number }) {
  const video = useRef<HTMLVideoElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const finished = useRef(false);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [position, setPosition] = useState(0);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState('');
  const duration = end - start;
  useEffect(() => {
    const el = video.current;
    if (!el) return;
    let frame = 0;
    function stop() {
      if (!el) return;
      finished.current = true;
      el.pause();
      el.currentTime = Math.max(start, end - 0.001);
      setPosition(duration);
    }
    function update() {
      if (!el || el.readyState < 1) return;
      if (el.currentTime < start) el.currentTime = start;
      if (el.currentTime >= end) {
        stop();
        return;
      }
      setPosition(finished.current ? duration : Math.max(0, el.currentTime - start));
    }
    function tick() {
      update();
      if (!el?.paused) frame = requestAnimationFrame(tick);
    }
    function onPlay() {
      if (finished.current || el!.currentTime >= end - 0.001) {
        finished.current = false;
        el!.currentTime = start;
      }
      setPlaying(true);
      cancelAnimationFrame(frame);
      tick();
    }
    function onPause() {
      setPlaying(false);
      cancelAnimationFrame(frame);
      update();
    }
    function initialize() {
      if (!Number.isFinite(el!.duration) || end > el!.duration + 0.1 || duration <= 0) {
        setError('保存した区間が動画の長さを超えています。範囲を編集してください。');
        return;
      }
      finished.current = false;
      el!.currentTime = start;
      setPosition(0);
      setReady(true);
    }
    el.addEventListener('loadedmetadata', initialize);
    el.addEventListener('timeupdate', update);
    el.addEventListener('seeking', update);
    el.addEventListener('play', onPlay);
    el.addEventListener('pause', onPause);
    if (el.readyState >= 1) initialize();
    return () => {
      el.pause();
      cancelAnimationFrame(frame);
      el.removeEventListener('loadedmetadata', initialize);
      el.removeEventListener('timeupdate', update);
      el.removeEventListener('seeking', update);
      el.removeEventListener('play', onPlay);
      el.removeEventListener('pause', onPause);
    };
  }, [src, start, end, duration]);
  async function play(restart = false) {
    const el = video.current;
    if (!el || !ready) return;
    if (restart || finished.current) {
      finished.current = false;
      el.currentTime = start;
      setPosition(0);
    }
    try {
      await el.play();
      setError('');
    } catch {
      setError('再生ボタンをもう一度押してください。');
    }
  }
  return (
    <div className="cell-player" ref={container}>
      <div className="video-frame">
        <video
          ref={video}
          src={src}
          playsInline
          preload="auto"
          disablePictureInPicture
          controlsList="nodownload"
          aria-label="保存したCell"
          onError={() => setError('動画を読み込めませんでした。接続を確認して開き直してください。')}
        />
      </div>
      <CellControls
        playing={playing}
        position={position}
        duration={duration}
        disabled={!ready}
        onToggle={() => (playing ? video.current?.pause() : void play())}
        onRestart={() => void play(true)}
        onSeek={(offset) => {
          if (!video.current) return;
          finished.current = offset >= duration;
          if (finished.current) video.current.pause();
          video.current.currentTime = Math.min(end - 0.001, start + offset);
          setPosition(offset);
        }}
        onFullscreen={() => {
          void container.current?.requestFullscreen().catch(() => {});
        }}
      />
      <button
        className="cell-volume text-button"
        aria-label={muted ? '音を出す' : '消音'}
        onClick={() => {
          if (video.current) video.current.muted = !muted;
          setMuted(!muted);
        }}
      >
        {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
      </button>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

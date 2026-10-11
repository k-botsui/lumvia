'use client';
import { useEffect, useRef, useState } from 'react';
import { Media } from '@/lib/api';
import { loadYoutube, YoutubePlayer } from '@/lib/youtube';
import { CellControls } from './cell-player';

export function LinkCellPlayer({
  media,
  start,
  end,
  onDuration,
}: {
  media: Media;
  start: number;
  end: number;
  onDuration?: (duration: number) => void;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const youtube = useRef<YoutubePlayer | null>(null);
  const readyRef = useRef(false);
  const atEnd = useRef(false);
  const current = useRef(start);
  const playingRef = useRef(false);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [position, setPosition] = useState(0);
  const [error, setError] = useState('');
  const [hint, setHint] = useState('');
  const [attempt, setAttempt] = useState(0);
  const durationCallback = useRef(onDuration);
  useEffect(() => {
    durationCallback.current = onDuration;
  }, [onDuration]);
  const provider = media.source.provider;
  const externalId = media.source.external_id || '';
  const duration = end - start;
  const range = { videoId: externalId, startSeconds: start, endSeconds: end };
  function tiktok(type: 'play' | 'pause' | 'seekTo', value?: number) {
    frame.current?.contentWindow?.postMessage(
      { 'x-tiktok-player': true, type, ...(value !== undefined ? { value } : {}) },
      'https://www.tiktok.com',
    );
  }
  function play(restart = false) {
    if (!readyRef.current) return;
    setHint('');
    if (provider === 'youtube') {
      if (restart || atEnd.current) youtube.current?.loadVideoById(range);
      else youtube.current?.playVideo();
    } else {
      if (restart || atEnd.current) tiktok('seekTo', start);
      tiktok('play');
    }
    if (restart || atEnd.current) {
      current.current = start;
      setPosition(0);
    }
    atEnd.current = false;
  }
  function pause() {
    if (provider === 'youtube') youtube.current?.pauseVideo();
    else tiktok('pause');
  }
  useEffect(() => {
    let disposed = false,
      poll = 0,
      stopTimer = 0;
    let pendingSeekUntil = 0;
    const el = provider === 'youtube' ? document.createElement('iframe') : frame.current;
    if (provider === 'youtube' && el && host.current) {
      el.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(externalId)}?enablejsapi=1&playsinline=1&controls=0&disablekb=1&start=${Math.floor(start)}&end=${Math.ceil(end)}&origin=${encodeURIComponent(window.location.origin)}`;
      el.title = 'YouTubeのCell';
      el.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
      el.allowFullscreen = true;
      el.referrerPolicy = 'strict-origin-when-cross-origin';
      el.setAttribute(
        'sandbox',
        'allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation',
      );
      host.current.append(el);
      frame.current = el;
    }
    readyRef.current = false;
    atEnd.current = false;
    playingRef.current = false;
    current.current = start;
    function state(value: boolean) {
      playingRef.current = value;
      setPlaying(value);
    }
    function stop() {
      if (atEnd.current) return;
      atEnd.current = true;
      clearTimeout(stopTimer);
      if (provider === 'youtube') {
        youtube.current?.pauseVideo();
        youtube.current?.seekTo(Math.max(start, end - 0.025), true);
      } else {
        tiktok('pause');
        tiktok('seekTo', Math.max(start, end - 0.025));
      }
      current.current = end;
      state(false);
      setPosition(duration);
    }
    function update(seconds: number, actualDuration: number) {
      if (
        !Number.isFinite(seconds) ||
        !Number.isFinite(actualDuration) ||
        actualDuration <= 0 ||
        actualDuration > 3600
      )
        return;
      durationCallback.current?.(actualDuration);
      if (end > actualDuration + 0.1) {
        if (provider === 'youtube') youtube.current?.pauseVideo();
        else tiktok('pause');
        setError('保存した区間が動画の長さを超えています。範囲を編集してください。');
        return;
      }
      current.current = seconds;
      if (performance.now() < pendingSeekUntil) return;
      if (seconds < start - 0.1) {
        pendingSeekUntil = performance.now() + 700;
        if (provider === 'youtube') youtube.current?.seekTo(start, true);
        else tiktok('seekTo', start);
        return;
      }
      if (seconds >= end && !atEnd.current) {
        stop();
        return;
      }
      setPosition(atEnd.current ? duration : Math.max(0, Math.min(duration, seconds - start)));
      clearTimeout(stopTimer);
      if (provider === 'tiktok' && playingRef.current && !atEnd.current) {
        stopTimer = window.setTimeout(stop, Math.max(0, end - seconds) * 1000);
      }
    }
    const receive = (event: MessageEvent) => {
      if (
        provider !== 'tiktok' ||
        event.origin !== 'https://www.tiktok.com' ||
        event.source !== el?.contentWindow ||
        !event.data ||
        typeof event.data !== 'object' ||
        event.data['x-tiktok-player'] !== true
      )
        return;
      const data = event.data;
      if (data.type === 'onPlayerReady') {
        readyRef.current = true;
        setReady(true);
        setError('');
        setHint('');
        pendingSeekUntil = performance.now() + 700;
        tiktok('seekTo', start);
        tiktok('play');
      } else if (data.type === 'onStateChange' && typeof data.value === 'number') {
        if (data.value === 1 && atEnd.current) {
          atEnd.current = false;
          pendingSeekUntil = performance.now() + 700;
          current.current = start;
          tiktok('seekTo', start);
        }
        state(data.value === 1);
        if (data.value !== 1) clearTimeout(stopTimer);
        else if (!atEnd.current)
          stopTimer = window.setTimeout(stop, Math.max(0, end - current.current) * 1000);
      } else if (
        data.type === 'onCurrentTime' &&
        data.value &&
        data.value.currentTime >= 0 &&
        data.value.currentTime <= data.value.duration + 1
      ) {
        update(data.value.currentTime, data.value.duration);
      } else if (data.type === 'onPlayerError') {
        if (data.value?.errorCode === 3002) setHint('プレーヤー内の再生ボタンを押してください。');
        else setError('TikTokでこの動画を再生できません。元サイトで開くか、動画ファイルを追加してください。');
      }
    };
    window.addEventListener('message', receive);
    const timeout = window.setTimeout(() => {
      if (!readyRef.current && provider === 'tiktok')
        setHint('TikTok内の再生ボタンを押すと、保存した範囲を再生できます。');
      else if (!readyRef.current)
        setError('プレーヤーに接続できませんでした。再試行するか、元サイトで開いてください。');
      else if (!playingRef.current && !atEnd.current)
        setHint('再生が始まらない場合は、プレーヤー内の再生ボタンを押してください。');
    }, 12000);
    if (provider === 'youtube' && el) {
      void loadYoutube()
        .then((api) => {
          if (disposed) return;
          youtube.current = new api.Player(el, {
            events: {
              onReady: ({ target }) => {
                if (disposed) return;
                readyRef.current = true;
                setReady(true);
                target.loadVideoById({ videoId: externalId, startSeconds: start, endSeconds: end });
                poll = window.setInterval(() => {
                  if (disposed || !youtube.current) return;
                  update(youtube.current.getCurrentTime(), youtube.current.getDuration());
                }, 50);
              },
              onStateChange: ({ data, target }) => {
                if (disposed) return;
                if (data === 1 && atEnd.current) {
                  atEnd.current = false;
                  pendingSeekUntil = performance.now() + 700;
                  target.loadVideoById({ videoId: externalId, startSeconds: start, endSeconds: end });
                }
                state(data === 1);
                if (data === 0 && !atEnd.current) stop();
              },
              onError: ({ data }) => {
                if (disposed) return;
                state(false);
                setError(
                  [101, 150].includes(data)
                    ? 'この動画はYouTubeが埋め込み再生を許可していません。元サイトで開くか、動画ファイルを追加してください。'
                    : data === 100
                      ? 'この動画は削除されたか、非公開になっています。'
                      : 'YouTubeでこの動画を再生できません。元サイトで開くか、動画ファイルを追加してください。',
                );
              },
              onAutoplayBlocked: () => {
                if (!disposed) setHint('再生ボタンを押してください。');
              },
            },
          });
        })
        .catch((e: Error) => {
          if (!disposed) setError(e.message);
        });
    }
    return () => {
      disposed = true;
      clearTimeout(timeout);
      clearTimeout(stopTimer);
      clearInterval(poll);
      window.removeEventListener('message', receive);
      if (provider === 'youtube') {
        if (el?.isConnected && readyRef.current) youtube.current?.pauseVideo();
        youtube.current?.destroy();
        youtube.current = null;
        el?.remove();
        frame.current = null;
      } else tiktok('pause');
    };
  }, [provider, externalId, start, end, duration, attempt]);
  const src =
    provider === 'youtube'
      ? `https://www.youtube-nocookie.com/embed/${encodeURIComponent(externalId)}?enablejsapi=1&playsinline=1&controls=0&disablekb=1&start=${Math.floor(start)}&end=${Math.ceil(end)}`
      : `https://www.tiktok.com/player/v1/${encodeURIComponent(externalId)}?autoplay=1&progress_bar=0&timestamp=0&description=0&music_info=0&loop=0`;
  return (
    <div className="cell-player link-cell-player">
      <div className={`reference-player ${provider} loaded`}>
        {provider === 'youtube' ? (
          <div ref={host} className="youtube-cell-host" />
        ) : (
          <iframe
            key={attempt}
            ref={frame}
            src={src}
            title={`${media.source.label} · ${media.title}`}
            allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation"
          />
        )}
      </div>
      <CellControls
        playing={playing}
        position={position}
        duration={duration}
        disabled={!ready || !!error}
        onToggle={() => (playing ? pause() : play())}
        onRestart={() => play(true)}
        onSeek={(offset) => {
          atEnd.current = offset >= duration;
          if (atEnd.current) pause();
          const seconds = Math.min(end - 0.025, start + offset);
          current.current = seconds;
          if (provider === 'youtube') youtube.current?.seekTo(seconds, true);
          else tiktok('seekTo', seconds);
          setPosition(offset);
        }}
      />
      {hint && (
        <p className="muted" role="status">
          {hint}
        </p>
      )}
      {error && (
        <div className="error-message" role="alert">
          {error}
          <button
            className="text-button"
            onClick={() => {
              setError('');
              setHint('');
              setReady(false);
              setPlaying(false);
              setPosition(0);
              setAttempt(attempt + 1);
            }}
          >
            再試行
          </button>
        </div>
      )}
    </div>
  );
}

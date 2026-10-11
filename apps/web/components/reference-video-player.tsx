'use client';
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Media } from '@/lib/api';
import { loadYoutube, YoutubePlayer } from '@/lib/youtube';

export type ReferencePlayback = { start?: number; end?: number; play: boolean };
export type ReferenceVideoHandle = { show: (request: ReferencePlayback) => void };

// Full playback has no end boundary. Inspecting a scene also clears any previous preview boundary.
export const ReferenceVideoPlayer = forwardRef<
  ReferenceVideoHandle,
  {
    media: Media;
    initialTime: number;
    initialEnd?: number;
    onTime: (position: number, duration: number) => void;
  }
>(function ReferenceVideoPlayer({ media, initialTime, initialEnd, onTime }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const youtube = useRef<YoutubePlayer | null>(null);
  const ready = useRef(false);
  const request = useRef<ReferencePlayback>({
    start: initialTime / 1000,
    end: initialEnd === undefined ? undefined : initialEnd / 1000,
    play: true,
  });
  const callback = useRef(onTime);
  const stopTimer = useRef(0);
  const seekTimer = useRef(0);
  const playing = useRef(false);
  const position = useRef(initialTime / 1000);
  const stopped = useRef(false);
  const seekUntil = useRef(0);
  const [hint, setHint] = useState('');
  const provider = media.source.provider;
  const externalId = media.source.external_id || '';
  useEffect(() => {
    callback.current = onTime;
  }, [onTime]);
  function command(type: 'play' | 'pause' | 'seekTo', value?: number) {
    if (provider === 'youtube') {
      if (type === 'play') youtube.current?.playVideo();
      else if (type === 'pause') youtube.current?.pauseVideo();
      else if (value !== undefined) youtube.current?.seekTo(value, true);
    } else
      frame.current?.contentWindow?.postMessage(
        { 'x-tiktok-player': true, type, ...(value === undefined ? {} : { value }) },
        'https://www.tiktok.com',
      );
  }
  function apply(next: ReferencePlayback) {
    clearTimeout(stopTimer.current);
    clearTimeout(seekTimer.current);
    request.current = next;
    stopped.current = false;
    if (next.start !== undefined) {
      position.current = next.start;
      seekUntil.current = performance.now() + 700;
    }
    if (!ready.current) return;
    const send = () => {
      if (next.start !== undefined) command('seekTo', next.start);
      if (next.play) command('play');
    };
    // Rapid handle movements are coalesced so the remote player receives the final position.
    if (next.start !== undefined) seekTimer.current = window.setTimeout(send, 120);
    else send();
  }
  useImperativeHandle(ref, () => ({ show: apply }));
  useEffect(() => {
    let disposed = false;
    let poll = 0;
    ready.current = false;
    const el = provider === 'youtube' ? document.createElement('iframe') : frame.current;
    function stop() {
      const end = request.current.end;
      if (end === undefined || stopped.current || disposed) return;
      stopped.current = true;
      playing.current = false;
      clearTimeout(stopTimer.current);
      clearTimeout(seekTimer.current);
      command('pause');
      command('seekTo', Math.max(request.current.start ?? 0, end - 0.025));
    }
    function schedule() {
      clearTimeout(stopTimer.current);
      const end = request.current.end;
      if (end !== undefined && playing.current && !stopped.current)
        stopTimer.current = window.setTimeout(stop, Math.max(0, end - position.current) * 1000);
    }
    function update(at: number, duration: number) {
      if (
        !Number.isFinite(at) ||
        !Number.isFinite(duration) ||
        at < 0 ||
        at > duration + 1 ||
        duration <= 0 ||
        duration > 3600
      )
        return;
      callback.current(at, duration);
      if (performance.now() < seekUntil.current) return;
      position.current = at;
      if (request.current.end !== undefined && at >= request.current.end) stop();
      else schedule();
    }
    function state(value: number) {
      // A native replay after a completed preview returns to normal viewing.
      if (value === 1 && stopped.current) {
        request.current = { play: true };
        stopped.current = false;
      }
      playing.current = value === 1;
      schedule();
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
        ready.current = true;
        apply(request.current);
      } else if (data.type === 'onCurrentTime' && data.value)
        update(data.value.currentTime, data.value.duration);
      else if (data.type === 'onStateChange' && typeof data.value === 'number') state(data.value);
      else if (data.type === 'onPlayerError')
        setHint(
          data.value?.errorCode === 3002
            ? 'プレーヤー内の再生ボタンを押してください。'
            : 'TikTokで再生できません。元サイトで開くか、動画ファイルを追加してください。',
        );
    };
    window.addEventListener('message', receive);
    if (provider === 'youtube' && el && host.current) {
      el.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(externalId)}?enablejsapi=1&playsinline=1&origin=${encodeURIComponent(window.location.origin)}`;
      el.title = `${media.source.label} · ${media.title}`;
      el.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
      el.allowFullscreen = true;
      el.referrerPolicy = 'strict-origin-when-cross-origin';
      el.setAttribute(
        'sandbox',
        'allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation',
      );
      host.current.append(el);
      frame.current = el;
      void loadYoutube()
        .then((api) => {
          if (disposed) return;
          youtube.current = new api.Player(el, {
            events: {
              onReady: () => {
                if (disposed) return;
                ready.current = true;
                apply(request.current);
                poll = window.setInterval(() => {
                  if (youtube.current && !disposed)
                    update(youtube.current.getCurrentTime(), youtube.current.getDuration());
                }, 100);
              },
              onStateChange: ({ data }) => {
                if (!disposed) state(data);
              },
              onError: () => {
                if (!disposed)
                  setHint('YouTubeで再生できません。元サイトで開くか、動画ファイルを追加してください。');
              },
              onAutoplayBlocked: () => {
                if (!disposed) setHint('プレーヤー内の再生ボタンを押してください。');
              },
            },
          });
        })
        .catch((e: Error) => {
          if (!disposed) setHint(e.message);
        });
    }
    return () => {
      disposed = true;
      clearTimeout(stopTimer.current);
      clearTimeout(seekTimer.current);
      clearInterval(poll);
      window.removeEventListener('message', receive);
      if (provider === 'youtube') {
        youtube.current?.destroy();
        youtube.current = null;
        el?.remove();
        frame.current = null;
      } else command('pause');
    };
    // The frame stays mounted while trimming; changing a boundary must not reload the video.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, externalId]);
  return (
    <>
      {provider === 'youtube' ? (
        <div ref={host} className="youtube-reference-host" />
      ) : (
        <iframe
          ref={frame}
          src={`https://www.tiktok.com/player/v1/${encodeURIComponent(externalId)}?autoplay=1&description=0&music_info=0&loop=0`}
          title={`${media.source.label} · ${media.title}`}
          allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
          sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation"
        />
      )}
      {hint && (
        <p className="reference-help" role="status">
          {hint}
        </p>
      )}
    </>
  );
});

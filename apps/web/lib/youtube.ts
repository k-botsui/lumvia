export interface YoutubePlayer {
  cueVideoById: (range: { videoId: string; startSeconds: number; endSeconds: number }) => void;
  loadVideoById: (range: { videoId: string; startSeconds: number; endSeconds: number }) => void;
  playVideo: () => void;
  pauseVideo: () => void;
  seekTo: (seconds: number, ahead: boolean) => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  getPlayerState: () => number;
  destroy: () => void;
}
interface YoutubeApi {
  Player: new (
    element: HTMLElement,
    options: {
      events: {
        onReady: (event: { target: YoutubePlayer }) => void;
        onStateChange: (event: { data: number; target: YoutubePlayer }) => void;
        onError: (event: { data: number }) => void;
        onAutoplayBlocked: () => void;
      };
    },
  ) => YoutubePlayer;
}
declare global {
  interface Window {
    YT?: YoutubeApi;
    onYouTubeIframeAPIReady?: () => void;
  }
}
let loading: Promise<YoutubeApi> | undefined;
// Load the official player API only after a user opens or plays a YouTube Cell.
export function loadYoutube(): Promise<YoutubeApi> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (loading) return loading;
  loading = new Promise<YoutubeApi>((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    const script = document.createElement('script');
    const timeout = window.setTimeout(() => fail(), 12000);
    function fail() {
      clearTimeout(timeout);
      window.onYouTubeIframeAPIReady = previous;
      script.remove();
      reject(new Error('YouTubeに接続できませんでした。もう一度お試しください。'));
    }
    window.onYouTubeIframeAPIReady = () => {
      clearTimeout(timeout);
      window.onYouTubeIframeAPIReady = previous;
      previous?.();
      if (window.YT?.Player) resolve(window.YT);
      else fail();
    };
    script.src = 'https://www.youtube.com/iframe_api';
    script.async = true;
    script.onerror = fail;
    document.head.append(script);
  }).catch((error) => {
    loading = undefined;
    throw error;
  });
  return loading;
}

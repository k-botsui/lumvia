'use client';
import { useUploadLimits } from '@/lib/upload-limits';
import { useRef, useState } from 'react';
import { UploadCloud, FileVideo, CheckCircle2, XCircle, X, Play, Loader2 } from 'lucide-react';
import { api, upload, bytes } from '@/lib/api';
import { destinationData } from '@/lib/groups';
interface UploadItem {
  id: string;
  file: File;
  progress: number;
  state: 'waiting' | 'uploading' | 'done' | 'failed';
  error?: string;
}
export function Uploader({
  onComplete,
  destination = '',
  onBusyChange,
}: {
  onComplete: () => void;
  destination?: string;
  onBusyChange?: (busy: boolean) => void;
}) {
  const uploadLimits = useUploadLimits();
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function add(files: File[]) {
    if (busy || !files.length) return;
    if (files.length > 20) {
      setMessage('1回に追加できる動画は20本までです。');
      return;
    }
    setMessage('');
    const chosen = files.map((file) => ({
      id: crypto.randomUUID(),
      file,
      progress: 0,
      state: 'waiting' as const,
    }));
    setItems(chosen);
    setBusy(true);
    onBusyChange?.(true);
    abort.current = new AbortController();
    try {
      let batchId: string | undefined;
      for (const item of chosen) {
        if (abort.current.signal.aborted) break;
        const update = (patch: Partial<UploadItem>) =>
          setItems((all) => all.map((i) => (i.id === item.id ? { ...i, ...patch } : i)));
        if (item.file.size > uploadLimits.max_upload_bytes) {
          update({
            state: 'failed',
            error: `${bytes(uploadLimits.max_upload_bytes)}以下の動画を選んでください。`,
          });
          continue;
        }
        if (!/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(item.file.name)) {
          update({
            state: 'failed',
            error: /\.(jpe?g|png|heic|heif)$/i.test(item.file.name)
              ? '画像が渡されています。Macの「写真」では、動画を選んで「ファイル」→「書き出す」→「未編集のオリジナルを書き出す」を使い、書き出したMOV・MP4を追加してください。'
              : 'MP4・MOV・WebM・MKV・AVIの動画を選んでください。',
          });
          continue;
        }
        update({ state: 'uploading' });
        try {
          if (!batchId) batchId = (await api<{ id: string }>('/batches', { method: 'POST' })).id;
          await upload(
            item.file,
            batchId,
            (p) => update({ progress: p }),
            abort.current.signal,
            destinationData(destination),
          );
          update({ state: 'done', progress: 100 });
          onComplete();
        } catch (e) {
          update({ state: 'failed', error: (e as Error).message });
        }
      }
      if (abort.current.signal.aborted)
        setItems((all) =>
          all.map((i) =>
            i.state === 'waiting' ? { ...i, state: 'failed', error: 'キャンセルしました。' } : i,
          ),
        );
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
      onBusyChange?.(false);
    }
  }
  async function sample() {
    try {
      const response = await fetch('/sample.mp4');
      if (!response.ok) throw new Error('サンプルを読み込めませんでした。');
      const blob = await response.blob();
      await add([new File([blob], 'Lumvia サンプル — 3つのシーン.mp4', { type: 'video/mp4' })]);
    } catch (e) {
      setMessage((e as Error).message);
    }
  }
  return (
    <div className="upload-section">
      <div
        className={`dropzone ${drag ? 'dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const files = Array.from(e.dataTransfer.files);
          if (!files.length)
            setMessage(
              '動画本体を受け取れませんでした。「写真」から動画を書き出して、Finderのファイルを追加してください。',
            );
          else void add(files);
        }}
      >
        <div className="upload-symbol">
          <UploadCloud size={32} />
        </div>
        <h2>動画を、ここに。</h2>
        <p>ファイルをドラッグ＆ドロップして追加</p>
        <button className="button primary" disabled={busy} onClick={() => input.current?.click()}>
          <UploadCloud size={17} />
          ファイルを選ぶ
        </button>
        <input
          ref={input}
          aria-label="動画ファイル"
          type="file"
          accept=".mp4,.mov,.m4v,.webm,.mkv,.avi"
          multiple
          hidden
          onChange={(e) => {
            void add(Array.from(e.target.files ?? []));
            e.target.value = '';
          }}
        />
        <small>
          MP4・MOV・WebM・MKV・AVI / 1本{bytes(uploadLimits.max_upload_bytes)}・
          {Math.round(uploadLimits.max_duration_ms / 60000)}分まで
        </small>
      </div>
      <details className="photos-help">
        <summary>Macの「写真」から動画を追加するには</summary>
        <p>
          動画を選択
          →「ファイル」→「書き出す」→「未編集のオリジナルを書き出す」。保存先のMOV・MP4をFinderからここへドラッグするか、「ファイルを選ぶ」で追加します。iCloudの動画は、本体のダウンロード完了を待ってください。
        </p>
        <p>
          直接ドラッグするとプレビュー画像が渡される場合があります。Live
          Photosは、書き出したMOVの部分を追加できます。
        </p>
      </details>
      <div className="upload-note">
        <span>動画は自分のライブラリに保存されます。</span>
        <button className="text-button" onClick={sample} disabled={busy}>
          <Play size={14} />
          サンプル動画で試す
        </button>
      </div>
      {message && (
        <p className="error-message" role="alert">
          {message}
        </p>
      )}
      {items.length > 0 && (
        <div className="upload-list">
          <div className="section-heading">
            <h3>
              追加する動画{' '}
              <span>
                {items.filter((i) => i.state === 'done').length}/{items.length}
              </span>
            </h3>
            {busy && (
              <button className="text-button" onClick={() => abort.current?.abort()}>
                <X size={15} />
                残りをキャンセル
              </button>
            )}
          </div>
          {items.map((item) => (
            <div className="upload-item" key={item.id}>
              <FileVideo size={22} />
              <div>
                <strong>{item.file.name}</strong>
                <span>
                  {item.error ||
                    (item.state === 'done'
                      ? '追加しました。再生の準備をしています。'
                      : item.state === 'uploading'
                        ? `アップロード中 ${item.progress}%`
                        : bytes(item.file.size))}
                </span>
                {item.state === 'uploading' && (
                  <progress max={100} value={item.progress} aria-label={`${item.file.name}の進捗`} />
                )}
              </div>
              {item.state === 'done' ? (
                <CheckCircle2 className="success" size={20} />
              ) : item.state === 'failed' ? (
                <XCircle className="error" size={20} />
              ) : (
                <Loader2 size={18} className={item.state === 'uploading' ? 'spin' : ''} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

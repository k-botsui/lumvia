'use client';
import { useRef, useState } from 'react';
import { ImagePlus, Loader2, RefreshCw } from 'lucide-react';
import { api, Media } from '@/lib/api';

export function CoverPicker({ media, onChanged }: { media: Media; onChanged: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function save(file?: File) {
    if (file && file.size > 2 * 1024 * 1024) {
      setError('画像は2 MB以下で選んでください。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const data = new FormData();
      if (file) data.append('file', file);
      await api(`/media/${media.id}/${file ? 'cover' : 'reference-cover'}`, {
        method: file ? 'PUT' : 'POST',
        body: file ? data : undefined,
      });
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }
  return (
    <div className="cover-picker">
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-label="カバー画像"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void save(file);
        }}
      />
      <button className="button compact secondary" disabled={busy} onClick={() => input.current?.click()}>
        {busy ? <Loader2 size={15} className="spin" /> : <ImagePlus size={15} />} カバーを選ぶ
      </button>
      {media.source.provider === 'tiktok' && !media.assets.thumbnail && (
        <button className="text-button" disabled={busy} onClick={() => void save()}>
          <RefreshCw size={14} /> 画像を取得
        </button>
      )}
      <small className="muted">JPEG・PNG・WebP / 2 MBまで</small>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

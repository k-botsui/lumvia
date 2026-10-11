'use client';
import { useRef, useState } from 'react';
import { ImagePlus, Move } from 'lucide-react';
import { api, Group } from '@/lib/api';
import { HeaderFrameEditor } from './header-frame-editor';
import { defaultHeaderFrame, ShelfHeaderImage } from './shelf-header-image';

export function ShelfHeaderPicker({
  group,
  kind,
  onChanged,
}: {
  group: Group;
  kind: string;
  onChanged: (group: Group) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [adjusting, setAdjusting] = useState(false);
  return (
    <div className="shelf-header-picker">
      <span className="field-label">ヘッダー画像</span>
      {group.header_url && (
        <ShelfHeaderImage group={group} className="shelf-header-preview" alt={`${group.name}のヘッダー`} />
      )}
      <div className="shelf-header-actions">
        <button
          type="button"
          className="button secondary compact"
          disabled={busy}
          onClick={() => input.current?.click()}
        >
          <ImagePlus size={16} />
          {busy ? '保存中…' : group.header_url ? '画像を変更' : '画像を選ぶ'}
        </button>
        {group.header_url && (
          <button
            type="button"
            className="button secondary compact"
            disabled={busy}
            onClick={() => setAdjusting(true)}
          >
            <Move size={16} />
            表示位置を調整
          </button>
        )}
        {group.header_url && (
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await api(`/${kind}/${group.id}/header`, { method: 'DELETE' });
                onChanged({ ...group, header_url: null, header_frame: defaultHeaderFrame });
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            画像を外す
          </button>
        )}
        <small className="muted">JPEG・PNG・WebP / 50 MBまで・保存時に自動調整</small>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        aria-label="Shelfのヘッダー画像"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (!file) return;
          if (file.size > 50 * 1024 ** 2) {
            setError('画像は50 MB以下で選んでください。');
            return;
          }
          setBusy(true);
          setError('');
          const data = new FormData();
          data.append('file', file);
          try {
            onChanged(await api<Group>(`/${kind}/${group.id}/header`, { method: 'PUT', body: data }));
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      />
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {adjusting && group.header_url && (
        <HeaderFrameEditor
          group={group}
          kind={kind}
          onClose={() => setAdjusting(false)}
          onSaved={onChanged}
        />
      )}
    </div>
  );
}

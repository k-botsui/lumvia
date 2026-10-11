'use client';
import { useRef, useState } from 'react';
import { api, Group, HeaderFrame } from '@/lib/api';
import { Modal } from './ui/dialog';
import { defaultHeaderFrame, ShelfHeaderImage } from './shelf-header-image';

const clamp = (value: number) => Math.min(100, Math.max(0, value));

export function HeaderFrameEditor({
  group,
  kind,
  onClose,
  onSaved,
}: {
  group: Group;
  kind: string;
  onClose: () => void;
  onSaved: (group: Group) => void;
}) {
  const [frame, setFrame] = useState<HeaderFrame>(group.header_frame ?? defaultHeaderFrame);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const drag = useRef<{
    id: number;
    x: number;
    y: number;
    overflowX: number;
    overflowY: number;
    frame: HeaderFrame;
  } | null>(null);
  return (
    <Modal
      open
      onClose={() => !busy && onClose()}
      title="ヘッダーの表示位置"
      description="写真をドラッグして、見せたい部分を選びます。"
    >
      <div className="header-frame-editor">
        <div
          className="header-frame-drag"
          role="group"
          aria-label="写真の表示位置。矢印キーでも移動できます"
          tabIndex={0}
          onPointerDown={(event) => {
            if (event.button !== 0 || busy) return;
            const image = event.currentTarget.querySelector('img');
            if (!image?.naturalWidth) return;
            const bounds = event.currentTarget.getBoundingClientRect();
            const scale = Math.max(bounds.width / image.naturalWidth, bounds.height / image.naturalHeight);
            drag.current = {
              id: event.pointerId,
              x: event.clientX,
              y: event.clientY,
              overflowX: image.naturalWidth * scale * frame.zoom - bounds.width,
              overflowY: image.naturalHeight * scale * frame.zoom - bounds.height,
              frame,
            };
            event.currentTarget.setPointerCapture(event.pointerId);
            event.currentTarget.focus();
          }}
          onPointerMove={(event) => {
            const start = drag.current;
            if (!start || start.id !== event.pointerId) return;
            setFrame({
              ...start.frame,
              x: clamp(
                start.frame.x -
                  (start.overflowX > 0.5 ? ((event.clientX - start.x) / start.overflowX) * 100 : 0),
              ),
              y: clamp(
                start.frame.y -
                  (start.overflowY > 0.5 ? ((event.clientY - start.y) / start.overflowY) * 100 : 0),
              ),
            });
          }}
          onPointerUp={(event) => {
            if (drag.current?.id === event.pointerId) drag.current = null;
          }}
          onPointerCancel={() => (drag.current = null)}
          onLostPointerCapture={() => (drag.current = null)}
          onKeyDown={(event) => {
            if (busy || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
            event.preventDefault();
            const step = event.shiftKey ? 10 : 2;
            setFrame((current) => ({
              ...current,
              x: clamp(
                current.x + (event.key === 'ArrowLeft' ? step : event.key === 'ArrowRight' ? -step : 0),
              ),
              y: clamp(current.y + (event.key === 'ArrowUp' ? step : event.key === 'ArrowDown' ? -step : 0)),
            }));
          }}
        >
          <ShelfHeaderImage group={group} frame={frame} alt="ヘッダーのプレビュー" />
        </div>
        <div className="header-frame-controls">
          <label>
            <span>
              拡大 <output>{frame.zoom.toFixed(1)}倍</output>
            </span>
            <input
              type="range"
              min={1}
              max={3}
              step={0.05}
              value={frame.zoom}
              disabled={busy}
              onChange={(event) => setFrame({ ...frame, zoom: Number(event.target.value) })}
            />
          </label>
          <label>
            <span>左右の位置</span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={frame.x}
              disabled={busy}
              onChange={(event) => setFrame({ ...frame, x: Number(event.target.value) })}
            />
          </label>
          <label>
            <span>上下の位置</span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={frame.y}
              disabled={busy}
              onChange={(event) => setFrame({ ...frame, y: Number(event.target.value) })}
            />
          </label>
        </div>
        <div className="header-frame-card-preview">
          <span className="field-label">一覧のプレビュー</span>
          <ShelfHeaderImage group={group} frame={frame} alt="Shelf一覧のプレビュー" />
        </div>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => setFrame(defaultHeaderFrame)}
          >
            中央に戻す
          </button>
          <button type="button" className="button secondary" disabled={busy} onClick={onClose}>
            キャンセル
          </button>
          <button
            type="button"
            className="button primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                onSaved(
                  await api<Group>(`/${kind}/${group.id}/header`, {
                    method: 'PATCH',
                    body: JSON.stringify(frame),
                  }),
                );
                onClose();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? '保存中…' : '表示位置を保存'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

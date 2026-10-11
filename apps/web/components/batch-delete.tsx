'use client';
import { useState } from 'react';
import { api, Cell, Media } from '@/lib/api';
import { Modal } from './ui/dialog';

export function BatchDelete({
  items,
  onClose,
  onChanged,
  notify,
}: {
  items: (Media | Cell)[];
  onClose: () => void;
  onChanged: () => void;
  notify: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const media = items.filter((item): item is Media => !('media_id' in item));
  const cells = items.filter((item): item is Cell => 'media_id' in item);
  return (
    <Modal
      open
      onClose={() => {
        if (!busy) onClose();
      }}
      title={`${items.length}件を削除しますか？`}
      description="この操作は取り消せません。対象を確認してください。"
    >
      <p className="batch-delete-description">
        動画・リンク {media.length}件、Cell {cells.length}件を削除します。
        {media.length > 0 && '動画・リンクに保存したCellとメモ、Shelfへの登録も削除されます。'}
        {cells.length > 0 && 'Cellだけを削除する場合、元動画は残ります。'}元サービスの投稿は削除されません。
      </p>
      <ul className="batch-delete-items">
        {items.map((item) => (
          <li key={item.id}>
            <span>{'media_id' in item ? 'Cell' : item.storage_mode === 'REFERENCE' ? 'リンク' : '動画'}</span>
            {item.title}
          </li>
        ))}
      </ul>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions">
        <button className="button secondary" disabled={busy} onClick={onClose}>
          キャンセル
        </button>
        <button
          className="button danger"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError('');
            try {
              await api('/library/delete-batch', {
                method: 'POST',
                body: JSON.stringify({
                  media_ids: media.map((item) => item.id),
                  cell_ids: cells.map((item) => item.id),
                }),
              });
              onChanged();
              notify(`${items.length}件を削除しました`);
              onClose();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? '削除中…' : `${items.length}件を削除する`}
        </button>
      </div>
    </Modal>
  );
}

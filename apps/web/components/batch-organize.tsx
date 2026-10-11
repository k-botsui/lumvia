'use client';
import { useState } from 'react';
import { api, Cell, Group, Media } from '@/lib/api';
import { allShelves } from '@/lib/groups';
import { Modal } from './ui/dialog';

export function BatchOrganize({
  items,
  shelves,
  collections,
  onClose,
  onChanged,
  notify,
}: {
  items: (Media | Cell)[];
  shelves: Group[];
  collections: Group[];
  onClose: () => void;
  onChanged: () => void;
  notify: (message: string) => void;
}) {
  const [destination, setDestination] = useState('');
  const [newName, setNewName] = useState('');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function add() {
    if (!items.length || (!destination && !newName.trim())) return;
    setBusy(true);
    setError('');
    try {
      let target = destination;
      if (newName.trim()) {
        const shelf = await api<Group>('/shelves', {
          method: 'POST',
          body: JSON.stringify({ name: newName.trim(), color: '#7487b8' }),
        });
        target = 'shelves:' + shelf.id;
        setDestination(target);
        setNewName('');
      }
      const [kind, id] = target.split(':');
      await api(`/${kind}/${id}/batch`, {
        method: 'PUT',
        body: JSON.stringify({
          media_ids: items.filter((item) => !('media_id' in item)).map((item) => item.id),
          cell_ids: items.filter((item) => 'media_id' in item).map((item) => item.id),
        }),
      });
      onChanged();
      notify(items.length + '件をShelfに追加しました');
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open title="Shelfにまとめて追加" description={items.length + '件を選択中'} onClose={onClose}>
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <label>
          追加先のShelf
          <select
            disabled={busy || !!newName.trim()}
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          >
            <option value="">Shelfを選ぶ</option>
            {allShelves(shelves, collections).map((g) => (
              <option key={g.id} value={g.kind + ':' + g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <details>
          <summary>新しいShelfを作る</summary>
          <label className="batch-new-shelf">
            名前
            <input
              disabled={busy}
              value={newName}
              maxLength={100}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="新しいShelfの名前"
            />
          </label>
        </details>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <button type="button" className="text-button" disabled={busy} onClick={onClose}>
            キャンセル
          </button>
          <button className="button primary" disabled={busy || (!destination && !newName.trim())}>
            {busy ? '追加しています…' : items.length + '件を追加'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

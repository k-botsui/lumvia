'use client';
import { useState } from 'react';
import { api, Media, Cell, Group } from '@/lib/api';
import { Modal } from './ui/dialog';
import { allShelves } from '@/lib/groups';
export function Organize({
  item,
  shelves,
  collections,
  onClose,
  onChanged,
  notify,
}: {
  item: Media | Cell;
  shelves: Group[];
  collections: Group[];
  onClose: () => void;
  onChanged: () => void;
  notify: (s: string) => void;
}) {
  const isCell = 'media_id' in item;
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set([...(item.shelf_ids ?? []), ...(item.collection_ids ?? [])]),
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function toggle(kind: string, g: Group) {
    setBusy(true);
    setError('');
    const has = selected.has(g.id);
    try {
      await api(`/${kind}/${g.id}/items${has ? '/' + item.id : ''}`, {
        method: has ? 'DELETE' : 'PUT',
        body: has ? undefined : JSON.stringify(isCell ? { cell_id: item.id } : { media_id: item.id }),
      });
      setSelected((old) => {
        const result = new Set(old);
        if (has) result.delete(g.id);
        else result.add(g.id);
        return result;
      });
      onChanged();
      notify(has ? '整理先から外しました' : '整理先に保存しました');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="整理する" description={item.title}>
      <div className="organization-list">
        <section>
          <h3>Shelfを選ぶ</h3>
          {allShelves(shelves, collections).map((g) => (
            <label key={g.id}>
              <span className="shelf-dot" style={{ background: g.color }} />
              {g.name}
              <input
                type="checkbox"
                checked={selected.has(g.id)}
                disabled={busy}
                onChange={() => toggle(g.kind, g)}
              />
            </label>
          ))}
        </section>
        {!collections.length && !shelves.length && <p className="muted">先にShelfを作成してください。</p>}
        {error && <p className="error-message">{error}</p>}
        <div className="form-actions">
          <button className="button primary" onClick={onClose}>
            完了
          </button>
        </div>
      </div>
    </Modal>
  );
}

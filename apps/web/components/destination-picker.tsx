'use client';
import { Plus } from 'lucide-react';
import type { ShelfGroup } from '@/lib/groups';

export function DestinationPicker({
  groups,
  value,
  onChange,
  onCreate,
  disabled = false,
}: {
  groups: ShelfGroup[];
  value: string;
  onChange: (value: string) => void;
  onCreate: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="destination-picker">
      <label>
        追加先のShelf
        <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
          <option value="">ライブラリのみ</option>
          {groups.map((g) => (
            <option key={g.kind + g.id} value={`${g.kind}:${g.id}`}>
              {g.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="text-button" onClick={onCreate} disabled={disabled}>
        <Plus size={15} />
        Shelfを作成
      </button>
    </div>
  );
}

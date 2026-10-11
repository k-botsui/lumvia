'use client';
import { useState } from 'react';
import { Check, Folder } from 'lucide-react';

const palette = [
  ['#4f7bff', 'ブルー'],
  ['#8c7bd6', 'ラベンダー'],
  ['#d483a2', 'ローズ'],
  ['#d9a16c', 'アプリコット'],
  ['#b7a15e', 'サンド'],
  ['#74a48a', 'セージ'],
  ['#5f9eae', 'アクア'],
  ['#7c869a', 'スレート'],
] as const;

export function ColorPicker({ initial = '#4f7bff' }: { initial?: string }) {
  const [color, setColor] = useState(initial.toLowerCase());
  return (
    <fieldset className="color-picker">
      <legend>カラー</legend>
      <input type="hidden" name="color" value={color} />
      <div className="color-options" role="group" aria-label="カラーを選択">
        {palette.map(([value, label]) => (
          <button
            key={value}
            type="button"
            className="color-swatch"
            style={{ background: value }}
            aria-label={label}
            aria-pressed={color === value}
            onClick={() => setColor(value)}
          >
            {color === value && <Check size={18} strokeWidth={3} />}
          </button>
        ))}
        <label className="custom-color" title="好きな色を選ぶ">
          <span>＋</span>
          <input
            type="color"
            aria-label="カスタムカラー"
            value={color}
            onChange={(e) => setColor(e.target.value)}
          />
        </label>
      </div>
      <div className="color-preview" style={{ '--shelf-color': color } as React.CSSProperties}>
        <span className="color-preview-icon">
          <Folder size={22} />
        </span>
        <div>
          <strong>色のプレビュー</strong>
          <small>サイドバーや一覧に、この色が付きます</small>
        </div>
        <span className="shelf-dot" style={{ background: color }} />
      </div>
    </fieldset>
  );
}

'use client';
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export type ContextAction = { label: string; run: () => void; danger?: boolean };
export function ItemContextMenu({
  x,
  y,
  title,
  actions,
  onClose,
}: {
  x: number;
  y: number;
  title: string;
  actions: ContextAction[];
  onClose: () => void;
}) {
  const menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const el = menu.current!;
    const rect = el.getBoundingClientRect();
    el.style.left = `${Math.max(8, Math.min(x, window.innerWidth - rect.width - 8))}px`;
    el.style.top = `${Math.max(8, Math.min(y, window.innerHeight - rect.height - 8))}px`;
    el.querySelector<HTMLButtonElement>('button')?.focus();
    const outside = (event: PointerEvent) => {
      if (!el.contains(event.target as Node)) onClose();
    };
    window.addEventListener('pointerdown', outside);
    window.addEventListener('resize', onClose);
    return () => {
      window.removeEventListener('pointerdown', outside);
      window.removeEventListener('resize', onClose);
      if (document.activeElement === document.body || el.contains(document.activeElement)) previous?.focus();
    };
  }, [x, y, onClose]);
  return createPortal(
    <div
      ref={menu}
      className="item-context-menu"
      role="menu"
      tabIndex={-1}
      aria-label={title}
      style={{ left: x, top: y }}
      onContextMenu={(event) => event.preventDefault()}
      onKeyDown={(event) => {
        if (event.key === 'Escape' || event.key === 'Tab') {
          event.preventDefault();
          onClose();
          return;
        }
        const buttons = [...menu.current!.querySelectorAll<HTMLButtonElement>('button')];
        const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          buttons[(index + (event.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length]?.focus();
        }
      }}
    >
      <small>{title}</small>
      {actions.map((action) => (
        <button
          key={action.label}
          role="menuitem"
          className={action.danger ? 'danger-text' : ''}
          onClick={() => {
            onClose();
            action.run();
          }}
        >
          {action.label}
        </button>
      ))}
    </div>,
    document.body,
  );
}

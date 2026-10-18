'use client';
import { useEffect, useId, useLayoutEffect, useRef } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { AnimatePresence, animate, usePresence, useReducedMotion } from 'motion/react';
import { X } from 'lucide-react';
import { dialogOrigin } from '@/lib/dialog-origin';
import { registerDialog } from '@/lib/dialog-stack';

type SurfaceProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
  wide?: boolean;
  className?: string;
  actions?: React.ReactNode;
  transitionId?: string;
};
function Surface({
  title,
  description,
  children,
  wide = false,
  className = '',
  actions,
  transitionId,
}: SurfaceProps) {
  const panel = useRef<HTMLDivElement>(null),
    shade = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  const [present, safeToRemove] = usePresence();
  const reduced = useReducedMotion();
  const source = useRef(dialogOrigin(transitionId));
  useLayoutEffect(() => {
    const node = panel.current,
      overlay = shade.current;
    if (!node || !overlay) return;
    const target = node.parentElement!.getBoundingClientRect(),
      from = source.current;
    const x = from ? from.left + from.width / 2 - (target.left + target.width / 2) : 0;
    const y = from ? from.top + from.height / 2 - (target.top + target.height / 2) : 16;
    const scale = from ? Math.max(0.16, Math.min(0.94, from.width / node.offsetWidth)) : 0.96;
    const first = !initialized.current;
    initialized.current = true;
    const timing = reduced ? { duration: 0.1 } : { type: 'spring' as const, duration: 0.42, bounce: 0 };
    const animation = present
      ? animate(
          node,
          first
            ? {
                x: [reduced ? 0 : x, 0],
                y: [reduced ? 0 : y, 0],
                scale: [reduced ? 1 : scale, 1],
                opacity: [0, 1],
              }
            : { x: 0, y: 0, scale: 1, opacity: 1 },
          timing,
        )
      : animate(
          node,
          { x: reduced ? 0 : x, y: reduced ? 0 : y, scale: reduced ? 1 : scale, opacity: 0 },
          reduced ? { duration: 0.1 } : { type: 'spring', duration: 0.3, bounce: 0 },
        );
    const veil = animate(overlay, { opacity: present ? 1 : 0 }, { duration: 0.2 });
    let cancelled = false;
    if (!present)
      animation.then(() => {
        if (!cancelled) safeToRemove?.();
      });
    return () => {
      cancelled = true;
      animation.stop();
      veil.stop();
    };
  }, [present, reduced, safeToRemove]);
  return (
    <div className="modal-layer">
      <DialogPrimitive.Overlay forceMount ref={shade} className="modal-overlay" style={{ opacity: 0 }} />
      <div className="modal-position">
        <DialogPrimitive.Content
          forceMount
          ref={panel}
          className={`modal motion-modal ${wide ? 'wide' : ''} ${className}`}
          style={{ opacity: 0 }}
        >
          <div className="modal-heading">
            <div>
              <DialogPrimitive.Title>{title}</DialogPrimitive.Title>
              <DialogPrimitive.Description className={description ? 'muted' : 'sr-only'}>
                {description || title}
              </DialogPrimitive.Description>
            </div>
            <div className="modal-heading-actions">
              {actions}
              <DialogPrimitive.Close className="icon-button" aria-label="閉じる">
                <X size={19} />
              </DialogPrimitive.Close>
            </div>
          </div>
          {children}
        </DialogPrimitive.Content>
      </div>
    </div>
  );
}
export function Modal({ open, onClose, ...props }: SurfaceProps & { open: boolean; onClose: () => void }) {
  const [present, removeFromParent] = usePresence();
  const dialogId = useId();
  const close = useRef(onClose);
  useLayoutEffect(() => {
    close.current = onClose;
  });
  useEffect(() => {
    if (open && present) return registerDialog(() => close.current());
  }, [open, present]);
  useEffect(() => {
    if (!present && !open) removeFromParent?.();
  }, [present, open, removeFromParent]);
  return (
    <DialogPrimitive.Root open={open && present} onOpenChange={(value) => !value && onClose()}>
      <DialogPrimitive.Portal forceMount>
        <AnimatePresence
          onExitComplete={() => {
            if (!present) removeFromParent?.();
          }}
        >
          {open && present && <Surface key={dialogId} {...props} />}
        </AnimatePresence>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

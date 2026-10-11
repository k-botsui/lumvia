'use client';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
  className = '',
  actions,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  wide?: boolean;
  className?: string;
  actions?: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="modal-overlay" />
        <DialogPrimitive.Content className={`modal ${wide ? 'wide' : ''} ${className}`}>
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
                <X size={20} />
              </DialogPrimitive.Close>
            </div>
          </div>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

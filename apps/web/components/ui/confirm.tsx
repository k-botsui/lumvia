'use client';
import * as Alert from '@radix-ui/react-alert-dialog';
export function Confirm({
  open,
  onClose,
  title,
  description,
  onConfirm,
  pending,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  onConfirm: () => void;
  pending?: boolean;
}) {
  return (
    <Alert.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Alert.Portal>
        <Alert.Overlay className="modal-overlay" />
        <Alert.Content className="modal confirm">
          <Alert.Title>{title}</Alert.Title>
          <Alert.Description>{description}</Alert.Description>
          <div className="form-actions">
            <Alert.Cancel className="button secondary" disabled={pending}>
              キャンセル
            </Alert.Cancel>
            <button className="button danger" disabled={pending} onClick={onConfirm}>
              {pending ? '削除中…' : '削除する'}
            </button>
          </div>
        </Alert.Content>
      </Alert.Portal>
    </Alert.Root>
  );
}

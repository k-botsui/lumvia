'use client';
import * as Dropdown from '@radix-ui/react-dropdown-menu';
import { Settings, UserRound, LogOut } from 'lucide-react';
import { User } from '@/lib/api';

export function AccountMenu({
  user,
  onSettings,
  onLogout,
}: {
  user: User;
  onSettings: () => void;
  onLogout: () => void;
}) {
  return (
    <div className="account-tools">
      <button className="icon-button topbar-icon" aria-label="設定を開く" title="設定" onClick={onSettings}>
        <Settings size={20} />
      </button>
      <Dropdown.Root>
        <Dropdown.Trigger asChild>
          <button
            className="icon-button topbar-icon account-trigger"
            aria-label="ユーザーメニューを開く"
            title={user.name}
          >
            <UserRound size={20} />
          </button>
        </Dropdown.Trigger>
        <Dropdown.Portal>
          <Dropdown.Content className="account-popover" sideOffset={10} align="end">
            <div className="account-info">
              <strong>{user.name}</strong>
              <span>{user.email}</span>
              <small>あなただけのライブラリ</small>
            </div>
            <Dropdown.Separator className="account-separator" />
            <Dropdown.Item onSelect={onSettings}>
              <Settings size={16} />
              アカウントと設定
            </Dropdown.Item>
            <Dropdown.Item onSelect={onLogout}>
              <LogOut size={16} />
              ログアウト
            </Dropdown.Item>
          </Dropdown.Content>
        </Dropdown.Portal>
      </Dropdown.Root>
    </div>
  );
}

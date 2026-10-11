'use client';
import { useState } from 'react';
import { LogOut, Download, ShieldCheck } from 'lucide-react';
import { api, bytes, Stats, User } from '@/lib/api';
import { Logo } from './brand';
import { SupportContact } from './support-contact';
export function SettingsView({
  user,
  stats,
  notify,
  onLogout,
}: {
  user: User;
  stats?: Stats;
  notify: (s: string) => void;
  onLogout: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  return (
    <div className="settings-layout">
      <section className="settings-card">
        <h2>アカウント</h2>
        <div className="account-row">
          <span className="avatar big">{user.name.slice(0, 1)}</span>
          <div>
            <strong>{user.name}</strong>
            <p>{user.email}</p>
          </div>
          <button
            className="button secondary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onLogout();
              } catch (e) {
                setError((e as Error).message);
                setBusy(false);
              }
            }}
          >
            <LogOut size={16} />
            ログアウト
          </button>
        </div>
        <details>
          <summary>パスワードを変更</summary>
          <form
            className="form password-form"
            onSubmit={async (e) => {
              e.preventDefault();
              const form = e.currentTarget,
                data = new FormData(form);
              setBusy(true);
              setError('');
              try {
                await api('/auth/password', {
                  method: 'POST',
                  body: JSON.stringify(Object.fromEntries(data)),
                });
                notify('パスワードを変更しました');
                form.reset();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              現在のパスワード
              <input type="password" autoComplete="current-password" name="current_password" required />
            </label>
            <label>
              新しいパスワード
              <input
                type="password"
                autoComplete="new-password"
                name="new_password"
                minLength={12}
                maxLength={256}
                required
                placeholder="12文字以上"
              />
            </label>
            <div className="form-actions">
              <button className="button primary" disabled={busy}>
                パスワードを更新
              </button>
            </div>
          </form>
        </details>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
      </section>
      <section className="settings-card">
        <h2>ライブラリとデータ</h2>
        <div className="settings-row">
          <div>
            <strong>保存量と上限</strong>
            <p>
              動画ファイル {stats?.managed_count ?? 0} / {stats?.limits.managed ?? 500}本・リンク{' '}
              {stats?.reference_count ?? 0} / {stats?.limits.references ?? 2000}件・Cell{' '}
              {stats?.cell_count ?? 0} / {stats?.limits.cells ?? 2000}件
              <br />
              Cellは動画ごとに{stats?.limits.cells_per_media ?? 100}件、1区間
              {Math.floor((stats?.limits.clip_ms ?? 300000) / 60000)}分までです。
            </p>
          </div>
        </div>
        <div className="settings-row">
          <div>
            <strong>動画の合計時間</strong>
            <p>アップロードした動画の合計</p>
          </div>
          <b>{Math.floor((stats?.duration_ms ?? 0) / 60000)}分</b>
        </div>
        <div className="settings-row">
          <div>
            <strong>保存しているファイル</strong>
            <p>元動画・再生用ファイル・サムネイルの合計</p>
          </div>
          <b>{bytes(stats?.stored_bytes ?? 0)}</b>
        </div>
        <div className="settings-row">
          <div>
            <strong>ライブラリを書き出す</strong>
            <p>
              動画情報・保存したリンク・メモ・タグ・Cells・整理先をJSON形式で保存します。
              <br />
              アップロードした動画は、詳細画面からダウンロードできます。
            </p>
          </div>
          <a className="button secondary" href="/api/v1/library/export" download>
            <Download size={16} />
            書き出す
          </a>
        </div>
        <div className="settings-notice">
          <ShieldCheck size={20} />
          <p>
            動画と写真は、お使いのPC内に保存します。自分だけが使うライブラリです。共有・クラウド同期は行いません。
            <br />
            保存データは作業フォルダーと分けて保存します。スマホから使う場合も、保存先は自分のPCです。
            <br />
            アップロードした動画は外部サービスへ送信しません。
            <br />
            リンク追加時の情報取得、外部プレーヤーの表示、公開動画の場面画像の準備時には各サービスへ接続します。お問い合わせは、GitHubの窓口を自分で開いたときだけ接続します。利用状況の追跡や自動送信は行いません。
          </p>
        </div>
      </section>
      <SupportContact notify={notify} />
      <div className="version-note">
        <Logo />
        <span>ローカル版 0.1.0</span>
      </div>
    </div>
  );
}

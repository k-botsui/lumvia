'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import { Logo } from './brand';
import { HomeSculpture } from './home-sculpture';
export function Login({ onLogin }: { onLogin: () => void }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const options = useQuery({
    queryKey: ['auth-options'],
    queryFn: () => api<{ password: boolean; oidc: boolean }>('/auth/options'),
  });
  return (
    <main className="login-page">
      <div className="login-shell">
        <header className="login-header">
          <Logo />
        </header>
        <section className="login-brand" aria-labelledby="login-title">
          <div className="login-artwork">
            <HomeSculpture />
          </div>
          <div className="login-story">
            <h1 id="login-title">Lumvia</h1>
            <p className="login-tagline">動画・リンク・Cells</p>
          </div>
        </section>
        <section className="login-panel" aria-labelledby="login-form-title">
          <div className="login-form">
            <h2 id="login-form-title">ライブラリを開く</h2>
            {options.data?.oidc && (
              <button
                className="button primary full"
                onClick={() =>
                  window.location.assign(new URL('/api/v1/auth/oidc/login', window.location.origin).href)
                }
              >
                組織のアカウントでログイン
              </button>
            )}
            {options.data?.password !== false && (
              <form
                className="form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  setBusy(true);
                  setError('');
                  const data = new FormData(e.currentTarget);
                  try {
                    await api('/auth/login', {
                      method: 'POST',
                      body: JSON.stringify({ email: data.get('email'), password: data.get('password') }),
                    });
                    onLogin();
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label>
                  メールアドレス
                  <input
                    type="email"
                    name="email"
                    autoComplete="username"
                    required
                    placeholder="name@example.com"
                  />
                </label>
                <label>
                  パスワード
                  <input
                    type="password"
                    name="password"
                    autoComplete="current-password"
                    required
                    placeholder="パスワードを入力"
                  />
                </label>
                {error && (
                  <p className="error-message" role="alert">
                    {error}
                  </p>
                )}
                <button className="button primary full" disabled={busy}>
                  {busy ? <Loader2 className="spin" size={18} /> : null}ログイン
                </button>
                <p className="login-help">
                  <span>初期ログイン情報は、PCに保存した</span>
                  <span>ログイン情報ファイルで確認できます。</span>
                </p>
              </form>
            )}
            {options.isError && <p className="error-message">{options.error.message}</p>}
            <div className="privacy-note">
              <ShieldCheck size={17} aria-hidden="true" />
              <span>このPCにデータを保存します。</span>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

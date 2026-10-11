'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Copy, ExternalLink, MessageCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { Modal } from './ui/dialog';

export function SupportContact({ notify }: { notify: (message: string) => void }) {
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const support = useQuery({
    queryKey: ['support'],
    queryFn: () => api<{ github_url: string | null }>('/support'),
    enabled: open,
    retry: false,
  });
  return (
    <>
      <section className="settings-card">
        <div className="settings-row">
          <div>
            <h2>お問い合わせ</h2>
            <p>不具合や、使い方について。</p>
          </div>
          <button className="button secondary" onClick={() => setOpen(true)}>
            <MessageCircle size={16} />
            お問い合わせ
          </button>
        </div>
      </section>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="お問い合わせ"
        description="動画・写真・アカウント情報・ログは添付されません。"
      >
        <div className="form">
          <label>
            件名
            <input
              value={subject}
              maxLength={200}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="例：動画が再生できない"
            />
          </label>
          <label>
            内容
            <textarea
              value={body}
              maxLength={10000}
              rows={7}
              onChange={(e) => setBody(e.target.value)}
              placeholder="起きたことや、操作の手順を書いてください。"
            />
          </label>
          <p className="muted">
            入力内容はこの画面だけで保持します。GitHubの問い合わせは公開されるため、個人情報や非公開のリンクを書かないでください。
          </p>
          {support.isPending ? (
            <p className="muted">窓口を確認しています…</p>
          ) : support.isError ? (
            <p className="error-message" role="alert">
              {support.error.message}
            </p>
          ) : !support.data?.github_url ? (
            <p className="muted">問い合わせ窓口は準備中です。内容をコピーして手元に残せます。</p>
          ) : null}
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions support-actions">
            <button
              className="button secondary"
              disabled={!subject.trim() && !body.trim()}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    [subject.trim(), body.trim()].filter(Boolean).join('\n\n'),
                  );
                  setError('');
                  notify('問い合わせ文をコピーしました');
                } catch {
                  setError('コピーできませんでした。入力した内容を選択してコピーしてください。');
                }
              }}
            >
              <Copy size={16} />
              内容をコピー
            </button>
            {support.data?.github_url && (
              <a
                className="button primary"
                href={support.data.github_url}
                target="_blank"
                rel="noopener noreferrer"
                referrerPolicy="no-referrer"
              >
                <ExternalLink size={16} />
                GitHubの窓口を開く
              </a>
            )}
          </div>
          {support.data?.github_url && (
            <p className="muted">
              GitHubで内容を貼り付け、確認してから送信してください。この画面から自動送信することはありません。
            </p>
          )}
        </div>
      </Modal>
    </>
  );
}

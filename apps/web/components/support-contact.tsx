'use client';
import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Copy, ExternalLink, MessageCircle, Send } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { Modal } from './ui/dialog';

type Support = {
  github_url: string | null;
  repository: string | null;
  can_submit: boolean;
};
type Receipt = { issue_url: string; issue_number: number };

export function SupportContact({ notify }: { notify: (message: string) => void }) {
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const sending = useRef(false);
  const request = useRef<{ id: string; content: string } | null>(null);
  const support = useQuery({
    queryKey: ['support'],
    queryFn: () => api<Support>('/support'),
    enabled: open,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (sending.current || !support.data?.can_submit || uncertain || !subject.trim() || !body.trim()) return;
    sending.current = true;
    setBusy(true);
    setError('');
    const content = JSON.stringify([subject.trim(), body.trim()]);
    if (request.current?.content !== content) request.current = { id: crypto.randomUUID(), content };
    try {
      const result = await api<Receipt>('/support', {
        method: 'POST',
        body: JSON.stringify({
          request_id: request.current.id,
          subject: subject.trim(),
          body: body.trim(),
        }),
      });
      setReceipt(result);
      setSubject('');
      setBody('');
      request.current = null;
      notify(`お問い合わせを送信しました（Issue #${result.issue_number}）`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '送信できませんでした。入力内容は残しています。');
      if (
        cause instanceof ApiError &&
        ['SUPPORT_UNCERTAIN', 'SUPPORT_PENDING', 'NETWORK_ERROR'].includes(cause.code)
      ) {
        setUncertain(true);
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

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
        onClose={() => !sending.current && setOpen(false)}
        title="お問い合わせ"
        description="入力した件名と内容だけをGitHubへ送信します。動画・写真・アカウント情報・ログは添付されません。"
      >
        {receipt ? (
          <div className="form">
            <p role="status">
              お問い合わせを送信しました。GitHubにIssue #{receipt.issue_number}を作成しました。
            </p>
            <a
              className="button primary"
              href={receipt.issue_url}
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="no-referrer"
            >
              <ExternalLink size={16} />
              送信したIssueを見る
            </a>
            <button
              className="button secondary"
              onClick={() => {
                setReceipt(null);
                setError('');
                setUncertain(false);
              }}
            >
              別のお問い合わせを書く
            </button>
          </div>
        ) : (
          <form className="form" onSubmit={submit}>
            <label>
              件名
              <input
                value={subject}
                required
                maxLength={200}
                disabled={busy || uncertain}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="例：動画が再生できない"
              />
            </label>
            <label>
              内容
              <textarea
                value={body}
                required
                maxLength={10000}
                rows={7}
                disabled={busy || uncertain}
                onChange={(e) => setBody(e.target.value)}
                placeholder="起きたことや、操作の手順を書いてください。"
              />
            </label>
            <p className="muted">
              送信するとGitHub
              Issuesに公開されます。個人情報、パスワード、非公開のリンクは書かないでください。入力中の文章はこの画面だけで保持します。
            </p>
            {support.isPending ? (
              <p className="muted">GitHub接続を確認しています…</p>
            ) : support.isError ? (
              <p className="error-message" role="alert">
                {support.error.message}
              </p>
            ) : !support.data?.repository ? (
              <p className="muted">問い合わせ先が設定されていません。</p>
            ) : !support.data.can_submit ? (
              <p className="muted">問い合わせ窓口は準備中です。入力内容はコピーして残せます。</p>
            ) : (
              <p className="muted">送信先：{support.data.repository}（GitHubへのログインは不要です）</p>
            )}
            {error && (
              <p className="error-message" role="alert">
                {error}
              </p>
            )}
            {uncertain && (
              <p className="muted">
                重複を避けるため再送を停止しています。Issue一覧で送信結果を確認してください。
              </p>
            )}
            <div className="form-actions support-actions">
              <button
                type="button"
                className="button secondary"
                disabled={busy || (!subject.trim() && !body.trim())}
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
              <button
                type="submit"
                className="button primary"
                disabled={busy || uncertain || !support.data?.can_submit || !subject.trim() || !body.trim()}
              >
                <Send size={16} />
                {busy ? '送信中…' : '送信'}
              </button>
            </div>
            {support.data?.github_url && (
              <a
                href={support.data.github_url}
                target="_blank"
                rel="noopener noreferrer"
                referrerPolicy="no-referrer"
              >
                <ExternalLink size={14} />
                GitHubのIssue一覧を見る
              </a>
            )}
          </form>
        )}
      </Modal>
    </>
  );
}

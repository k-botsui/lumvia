'use client';
import { useEffect, useState } from 'react';
import { Link2, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Modal } from './ui/dialog';

type Result = {
  id: string;
  title: string;
  url: string;
  status: 'reachable' | 'broken' | 'unknown';
  reason: string;
  cell_count: number;
  shelf_names: string[];
  proof: string | null;
};
export function LinkCheck({
  onChanged,
  notify,
}: {
  onChanged: () => void;
  notify: (message: string) => void;
}) {
  const [online, setOnline] = useState(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState({ checked: 0, total: 0 });
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    const update = () => {
      setOnline(navigator.onLine);
      if (!navigator.onLine) {
        setDone(false);
        setSelected([]);
        setConfirm(false);
        setResults([]);
        setError('オフラインのため実行できませんでした。削除は行っていません。');
      }
    };
    update();
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);
  const chosen = results.filter(
    (item) => selected.includes(item.id) && item.status === 'broken' && item.proof,
  );
  const offline = () => {
    if (!navigator.onLine) throw new Error('オフラインのため実行できませんでした。削除は行っていません。');
  };
  async function scan() {
    setBusy(true);
    setDone(false);
    setResults([]);
    setSelected([]);
    setConfirm(false);
    setError('');
    try {
      offline();
      const targets = await api<{ media_ids: string[] }>('/library/link-check/targets');
      setProgress({ checked: 0, total: targets.media_ids.length });
      const items: Result[] = [];
      for (let i = 0; i < targets.media_ids.length; i += 10) {
        offline();
        const batch = await api<{ items: Result[] }>('/library/link-check', {
          method: 'POST',
          body: JSON.stringify({ media_ids: targets.media_ids.slice(i, i + 10) }),
        });
        offline();
        items.push(...batch.items);
        setResults([...items]);
        setProgress({ checked: items.length, total: targets.media_ids.length });
      }
      offline();
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
      setResults([]);
      setSelected([]);
      setConfirm(false);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button
        className="button secondary"
        disabled={!online}
        title={online ? 'ライブラリ全体のリンクを点検' : 'オフラインではリンク点検できません'}
        onClick={() => {
          setOpen(true);
          setDone(false);
          setResults([]);
          setSelected([]);
          setConfirm(false);
          setError('');
        }}
      >
        <Link2 size={16} /> リンクを点検
      </button>
      {open && (
        <Modal
          open
          title={confirm ? 'リンク切れを削除しますか？' : 'リンクの点検'}
          onClose={() => {
            if (!busy) setOpen(false);
          }}
        >
          <p className="muted">
            ライブラリ全体の保存リンクを点検します。関連CellsとShelfへの登録も対象です。通信エラー・ログイン制限は削除候補にしません。
          </p>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          {!confirm && (
            <>
              <div className="form-actions">
                <button className="button primary" disabled={!online || busy} onClick={scan}>
                  {busy ? (
                    <>
                      <Loader2 size={16} className="spin" /> {progress.checked} / {progress.total} 件を点検中
                    </>
                  ) : done ? (
                    'もう一度点検'
                  ) : (
                    'すべてのリンクを点検'
                  )}
                </button>
              </div>
              {done && (
                <p role="status">
                  到達できた {results.filter((i) => i.status === 'reachable').length}件 · リンク切れ{' '}
                  {results.filter((i) => i.status === 'broken').length}件 · 確認できない{' '}
                  {results.filter((i) => i.status === 'unknown').length}件
                </p>
              )}
              {done && results.some((i) => i.status === 'broken') && (
                <button
                  className="text-button"
                  onClick={() =>
                    setSelected(
                      results
                        .filter((i) => i.status === 'broken' && i.proof)
                        .slice(0, 100)
                        .map((i) => i.id),
                    )
                  }
                >
                  リンク切れをまとめて選択（100件まで）
                </button>
              )}
              <ul className="link-check-results">
                {results.map((item) => (
                  <li key={item.id}>
                    <label>
                      <input
                        type="checkbox"
                        disabled={!online || !done || busy || item.status !== 'broken' || !item.proof}
                        checked={selected.includes(item.id)}
                        onChange={(e) =>
                          setSelected((prev) =>
                            e.target.checked
                              ? prev.length < 100
                                ? [...prev, item.id]
                                : prev
                              : prev.filter((id) => id !== item.id),
                          )
                        }
                      />
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.status === 'reachable'
                            ? '到達できた'
                            : item.status === 'broken'
                              ? 'リンク切れ'
                              : '確認できない'}{' '}
                          · {item.reason}
                        </small>
                        <small>
                          関連Cells {item.cell_count}件 · Shelf {item.shelf_names.join('、') || 'なし'}
                        </small>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              {done && results.length === 0 && <p>点検するリンクはありません。</p>}
              <div className="form-actions">
                <button
                  className="button danger"
                  disabled={!online || !done || busy || !chosen.length}
                  onClick={() => setConfirm(true)}
                >
                  選んだ{chosen.length}件の削除を確認
                </button>
              </div>
            </>
          )}
          {confirm && (
            <>
              <p>
                リンク {chosen.length}件と関連Cells{' '}
                {chosen.reduce((total, item) => total + item.cell_count, 0)}
                件を削除します。Shelfは残し、対象の登録だけを取り除きます。元サービスの投稿は削除されません。この操作は取り消せません。
              </p>
              <ul className="link-check-results">
                {chosen.map((item) => (
                  <li key={item.id}>
                    <strong>{item.title}</strong>
                    <small>
                      Cells {item.cell_count}件 · Shelf {item.shelf_names.join('、') || 'なし'}
                    </small>
                  </li>
                ))}
              </ul>
              <div className="form-actions">
                <button className="button secondary" disabled={busy} onClick={() => setConfirm(false)}>
                  戻る
                </button>
                <button
                  className="button danger"
                  disabled={!online || !done || busy || !chosen.length}
                  onClick={async () => {
                    setBusy(true);
                    setError('');
                    try {
                      offline();
                      await api('/library/link-check/delete', {
                        method: 'POST',
                        body: JSON.stringify({ proofs: chosen.map((item) => item.proof) }),
                      });
                      onChanged();
                      notify(`${chosen.length}件のリンク切れを削除しました`);
                      setOpen(false);
                    } catch (e) {
                      setError((e as Error).message);
                      setDone(false);
                      setSelected([]);
                      setConfirm(false);
                      setResults([]);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {busy ? '再確認して削除中…' : `${chosen.length}件を削除する`}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}

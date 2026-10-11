'use client';
export default function Error({ reset }: { reset: () => void }) {
  return (
    <main className="error-page">
      <h1>ページを表示できませんでした</h1>
      <p>データは保存されています。もう一度お試しください。</p>
      <button className="button primary" onClick={reset}>
        再読み込み
      </button>
    </main>
  );
}

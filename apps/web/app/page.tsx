import { Suspense } from 'react';
import { Lumvia } from '@/components/lumvia';
export const dynamic = 'force-dynamic';
export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="boot">
          <img src="/favicon.svg" alt="" width="60" height="60" />
          <span>Lumvia</span>
        </div>
      }
    >
      <Lumvia />
    </Suspense>
  );
}

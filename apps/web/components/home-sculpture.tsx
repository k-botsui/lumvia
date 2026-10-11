'use client';
import { useEffect, useId, useRef } from 'react';

/** A local, procedural object. No photos, external textures, or tracking. */
export function HomeSculpture() {
  const host = useRef<HTMLDivElement>(null);
  const id = useId().replace(/:/g, '');
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let disposed = false;
    let release: (() => void) | undefined;
    void import('./home-scene')
      .then(({ mountSculpture }) => {
        if (!disposed) release = mountSculpture(element);
      })
      .catch(() => {
        if (!disposed) element.dataset.fallback = 'true';
      });
    return () => {
      disposed = true;
      release?.();
      delete element.dataset.ready;
      delete element.dataset.fallback;
    };
  }, []);
  return (
    <div className="home-object" ref={host} aria-hidden="true">
      <div className="object-light" />
      <div className="object-shadow" />
      <svg className="object-trace" viewBox="0 0 600 480" fill="none">
        <defs>
          <linearGradient
            id={`${id}-light`}
            x1="70"
            y1="350"
            x2="540"
            y2="270"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#afc2f5" stopOpacity="0" />
            <stop offset=".45" stopColor="#a4b9f4" />
            <stop offset=".75" stopColor="#fff" />
            <stop offset="1" stopColor="#d8d8e5" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M45 325C158 448 522 413 547 288"
          pathLength="1"
          stroke={`url(#${id}-light)`}
          strokeWidth="1.2"
        />
      </svg>
      <svg className="object-fallback" viewBox="0 0 64 64" fill="none">
        <defs>
          <linearGradient id={id} x1="16" y1="10" x2="54" y2="48" gradientUnits="userSpaceOnUse">
            <stop stopColor="#d4edff" />
            <stop offset=".45" stopColor="#849aff" />
            <stop offset="1" stopColor="#fff2df" />
          </linearGradient>
        </defs>
        <path d="M17 15Q17 10 23 13L40 22Q47 28 38 34L20 47Q17 50 17 44Z" fill={`url(#${id})`} />
        <path
          d="M17 44Q17 36 27 32L44 25Q52 22 52 32Q53 39 47 42L26 52Q17 57 17 44Z"
          fill={`url(#${id})`}
          stroke="#fff"
          strokeWidth=".35"
        />
      </svg>
    </div>
  );
}

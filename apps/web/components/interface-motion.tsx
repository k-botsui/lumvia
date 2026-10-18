'use client';
import { useEffect } from 'react';
export function InterfaceMotion({ location }: { location: string }) {
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        document.querySelector<HTMLInputElement>('.search-box input')?.focus();
      }
    };
    document.addEventListener('keydown', shortcut);
    return () => document.removeEventListener('keydown', shortcut);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.lumviaView = location.split(':')[0];
  }, [location]);
  return null;
}

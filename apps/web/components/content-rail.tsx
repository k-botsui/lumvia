'use client';
import { motion } from 'motion/react';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export function ContentRail({
  title,
  more,
  children,
  kind = 'media',
}: {
  title: string;
  more?: ReactNode;
  children: ReactNode;
  kind?: 'media' | 'cells' | 'shelves';
}) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  const [edges, setEdges] = useState({ start: true, end: true });
  useEffect(() => {
    const rail = ref.current;
    if (!rail) return;
    const update = () =>
      setEdges({
        start: rail.scrollLeft < 2,
        end: rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2,
      });
    const observer = new ResizeObserver(update);
    observer.observe(rail);
    for (const child of Array.from(rail.children)) observer.observe(child);
    rail.addEventListener('scroll', update, { passive: true });
    update();
    return () => {
      observer.disconnect();
      rail.removeEventListener('scroll', update);
    };
  }, [children]);
  function move(direction: number) {
    const rail = ref.current;
    if (!rail) return;
    const first = rail.firstElementChild as HTMLElement | null;
    const step = first
      ? first.getBoundingClientRect().width + (parseFloat(getComputedStyle(rail).columnGap) || 20)
      : rail.clientWidth;
    const count = Math.max(1, Math.floor(rail.clientWidth / step));
    rail.scrollBy({
      left: direction * step * count,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    });
  }
  return (
    <motion.section
      className={`content-rail-section rail-${kind}`}
      aria-labelledby={id}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ type: 'spring', stiffness: 240, damping: 28 }}
    >
      <div className="section-heading">
        <h2 id={id}>{title}</h2>
        <div className="rail-actions">
          {more}
          <div className="rail-buttons">
            <button
              className="icon-button"
              aria-label={`${title}を前へ送る`}
              disabled={edges.start}
              onClick={() => move(-1)}
            >
              <ChevronLeft size={18} />
            </button>
            <button
              className="icon-button"
              aria-label={`${title}を次へ送る`}
              disabled={edges.end}
              onClick={() => move(1)}
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </div>
      <div
        className="content-rail"
        ref={ref}
        role="region"
        aria-label={`${title}の一覧`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.target !== e.currentTarget) return;
          if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
            e.preventDefault();
            move(e.key === 'ArrowRight' ? 1 : -1);
          }
          if (e.key === 'Home' || e.key === 'End') {
            e.preventDefault();
            e.currentTarget.scrollTo({
              left: e.key === 'Home' ? 0 : e.currentTarget.scrollWidth,
              behavior: 'auto',
            });
          }
        }}
      >
        {children}
      </div>
    </motion.section>
  );
}

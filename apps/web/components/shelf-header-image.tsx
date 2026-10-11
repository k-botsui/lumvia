import { Group, HeaderFrame } from '@/lib/api';

export const defaultHeaderFrame: HeaderFrame = { x: 50, y: 50, zoom: 1 };

export function ShelfHeaderImage({
  group,
  frame = group.header_frame ?? defaultHeaderFrame,
  className = '',
  alt = '',
}: {
  group: Group;
  frame?: HeaderFrame;
  className?: string;
  alt?: string;
}) {
  return (
    <div className={`header-image ${className}`}>
      <img
        src={group.header_url!}
        alt={alt}
        draggable={false}
        style={{
          objectPosition: `${frame.x}% ${frame.y}%`,
          transform: `scale(${frame.zoom})`,
          transformOrigin: `${frame.x}% ${frame.y}%`,
        }}
      />
    </div>
  );
}

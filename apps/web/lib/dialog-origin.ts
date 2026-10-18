const origins = new Map<string, { left: number; top: number; width: number; height: number }>();
export function captureDialogOrigin(id: string) {
  const source = document.querySelector<HTMLElement>(`[data-media-surface="${CSS.escape(id)}"]`);
  if (!source) return;
  const rect = source.getBoundingClientRect();
  origins.set(`media-surface-${id}`, {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
  });
  if (origins.size > 12) origins.delete(origins.keys().next().value!);
}
export function dialogOrigin(id?: string) {
  return id ? origins.get(id) : undefined;
}
